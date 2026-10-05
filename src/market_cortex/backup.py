"""Encrypted, file-complete PostgreSQL/Parquet backup and isolated restore.

The passphrase and DSN are environment-only. The catalog ingestion lock holds
the manifest head stable while pg_dump and referenced artifacts are copied.
Restore requires an empty, separate database and an empty data directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from psycopg.conninfo import conninfo_to_dict

from .config import Settings
from .database import connect
from .storage import ArtifactStore, PostgresCatalog

MAGIC = b"MCBACKUP1"
SALT_BYTES = 16
NONCE_BYTES = 12
TAG_BYTES = 16
CHUNK = 1024 * 1024
LOCK_ID = 837_241_904


def _key(passphrase: str, salt: bytes) -> bytes:
    if len(passphrase) < 16:
        raise ValueError("backup passphrase must have at least 16 characters")
    return Scrypt(salt=salt, length=32, n=2 ** 15, r=8, p=1).derive(passphrase.encode("utf-8"))


def encrypt_file(source: Path, destination: Path, passphrase: str) -> None:
    salt, nonce = os.urandom(SALT_BYTES), os.urandom(NONCE_BYTES)
    encryptor = Cipher(algorithms.AES(_key(passphrase, salt)), modes.GCM(nonce)).encryptor()
    with source.open("rb") as infile, destination.open("wb") as outfile:
        outfile.write(MAGIC + salt + nonce)
        while block := infile.read(CHUNK):
            outfile.write(encryptor.update(block))
        outfile.write(encryptor.finalize())
        outfile.write(encryptor.tag)
        outfile.flush()
        os.fsync(outfile.fileno())


def decrypt_file(source: Path, destination: Path, passphrase: str) -> None:
    with source.open("rb") as infile:
        header = infile.read(len(MAGIC) + SALT_BYTES + NONCE_BYTES)
        if len(header) != len(MAGIC) + SALT_BYTES + NONCE_BYTES or not header.startswith(MAGIC):
            raise ValueError("unrecognized backup format")
        salt = header[len(MAGIC):len(MAGIC) + SALT_BYTES]
        nonce = header[-NONCE_BYTES:]
        payload_end = source.stat().st_size - TAG_BYTES
        if payload_end < len(header):
            raise ValueError("truncated backup")
        infile.seek(payload_end)
        tag = infile.read(TAG_BYTES)
        decryptor = Cipher(algorithms.AES(_key(passphrase, salt)), modes.GCM(nonce, tag)).decryptor()
        infile.seek(len(header))
        remaining = payload_end - len(header)
        try:
            with destination.open("wb") as outfile:
                while remaining:
                    block = infile.read(min(CHUNK, remaining))
                    if not block:
                        raise ValueError("truncated backup")
                    outfile.write(decryptor.update(block))
                    remaining -= len(block)
                outfile.write(decryptor.finalize())
        except (InvalidTag, ValueError):
            destination.unlink(missing_ok=True)
            raise ValueError("backup authentication failed") from None


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _tool(binary: str) -> str:
    path = shutil.which(binary)
    if path is None:
        raise RuntimeError(f"{binary} executable not found")
    return path


def _run_pg(binary: str, dsn: str, args: list[str]) -> None:
    info = conninfo_to_dict(dsn)
    mapping = {"dbname": "PGDATABASE", "host": "PGHOST", "port": "PGPORT", "user": "PGUSER",
               "password": "PGPASSWORD", "sslmode": "PGSSLMODE"}
    env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    env.update({target: str(info[source]) for source, target in mapping.items() if source in info})
    try:
        result = subprocess.run([_tool(binary), *args], env=env, capture_output=True,
                                timeout=900, check=False)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{binary} timed out") from None
    # stderr may contain a password-bearing DSN. Never surface it.
    if result.returncode:
        raise RuntimeError(f"{binary} failed with exit code {result.returncode}")


def _safe_member(name: str) -> bool:
    path = Path(name)
    return (bool(name) and "\\" not in name and ":" not in name and not path.is_absolute()
            and ".." not in path.parts and
            (name in {"manifest.json", "catalog.dump"} or
             name.startswith("artifacts/lake/") and name.endswith(".parquet")))


def backup(settings: Settings, destination: Path, passphrase: str) -> dict:
    if not settings.database_url:
        raise ValueError("database not configured")
    destination.parent.mkdir(parents=True, exist_ok=True)
    catalog = PostgresCatalog(settings.database_url, ArtifactStore(settings.data_root))
    with tempfile.TemporaryDirectory(prefix="market-cortex-backup-") as work:
        staging = Path(work)
        with connect(settings.database_url) as lock_connection:
            lock_connection.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
            try:
                head = catalog.head()
                artifacts = catalog.artifacts_for(head) if head else []
                if lock_connection.execute("SELECT to_regclass('context_files')").fetchone()[0]:
                    from .intelligence_store import ContextStore
                    artifacts += ContextStore(catalog).artifacts()
                dump = staging / "catalog.dump"
                _run_pg("pg_dump", settings.database_url, ["--format=custom", "--no-owner", "--no-privileges",
                                                            "--file", str(dump)])
                files = []
                for artifact in artifacts:
                    original = (settings.data_root / artifact.relative_path).resolve()
                    if not original.is_relative_to(settings.data_root.resolve()) or _sha(original) != artifact.content_hash:
                        raise OSError("referenced artifact missing or corrupted")
                    target = staging / "artifacts" / artifact.relative_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(original, target)
                    if _sha(target) != artifact.content_hash:
                        raise OSError("artifact changed during copy")
                    files.append({"path": artifact.relative_path, "sha256": artifact.content_hash,
                                  "rows": artifact.row_count})
                manifest = {"format": "MCBACKUP1", "created_at": datetime.now(timezone.utc).isoformat(),
                            "head_manifest_id": str(head) if head else None, "catalog_sha256": _sha(dump),
                            "artifacts": files}
                (staging / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")
                if catalog.head() != head:
                    raise RuntimeError("manifest head moved during backup")
            finally:
                lock_connection.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
        tar_path = staging / "bundle.tar"
        with tarfile.open(tar_path, "w") as tar:
            artifact_paths = sorted((staging / "artifacts").rglob("*.parquet")) if (staging / "artifacts").exists() else []
            for path in [staging / "manifest.json", dump, *artifact_paths]:
                tar.add(path, arcname=path.relative_to(staging).as_posix(), recursive=False)
        temp_output = destination.with_name(destination.name + ".partial")
        try:
            encrypt_file(tar_path, temp_output, passphrase)
            os.replace(temp_output, destination)
        finally:
            temp_output.unlink(missing_ok=True)
    return {"head_manifest_id": manifest["head_manifest_id"], "artifact_count": len(files),
            "encrypted_backup": str(destination)}


def restore(source: Path, destination_data_root: Path, restore_dsn: str, live_dsn: str | None,
            passphrase: str) -> dict:
    def database_identity(dsn: str) -> tuple[str, str, str]:
        info = conninfo_to_dict(dsn)
        return (info.get("host") or "localhost", info.get("port") or "5432", info.get("dbname") or "")
    if not restore_dsn or (live_dsn and database_identity(restore_dsn) == database_identity(live_dsn)):
        raise ValueError("restore requires a separate database connection")
    if destination_data_root.exists() and any(destination_data_root.iterdir()):
        raise ValueError("restore data directory must be empty")
    with tempfile.TemporaryDirectory(prefix="market-cortex-restore-") as work:
        staging = Path(work)
        archive = staging / "bundle.tar"
        decrypt_file(source, archive, passphrase)
        extraction = staging / "extracted"
        extraction.mkdir()
        with tarfile.open(archive, "r") as tar:
            seen = set()
            for member in tar:
                if not member.isfile() or not _safe_member(member.name) or member.name in seen:
                    raise ValueError("unsafe backup member")
                seen.add(member.name)
                target = extraction / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as infile, target.open("wb") as outfile:
                    shutil.copyfileobj(infile, outfile)
        manifest = json.loads((extraction / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("format") != "MCBACKUP1" or _sha(extraction / "catalog.dump") != manifest.get("catalog_sha256"):
            raise ValueError("backup catalog checksum mismatch")
        for file in manifest.get("artifacts", []):
            relative = file["path"]
            if not _safe_member("artifacts/" + relative):
                raise ValueError("unsafe artifact path")
            if _sha(extraction / "artifacts" / relative) != file["sha256"]:
                raise ValueError("backup artifact checksum mismatch")
        expected = {"manifest.json", "catalog.dump"} | {"artifacts/" + item["path"] for item in manifest["artifacts"]}
        if seen != expected:
            raise ValueError("backup member list mismatch")
        # pg_restore has no --clean. The target must be a new empty database.
        dbname = conninfo_to_dict(restore_dsn).get("dbname")
        if not dbname:
            raise ValueError("restore database name required")
        with connect(restore_dsn) as connection:
            count = connection.execute("""SELECT count(*) FROM pg_tables
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')""").fetchone()[0]
            if count:
                raise ValueError("restore database must be empty")
        _run_pg("pg_restore", restore_dsn, ["--exit-on-error", "--no-owner", "--no-privileges",
                                            "--dbname", dbname, str(extraction / "catalog.dump")])
        for file in manifest["artifacts"]:
            destination = destination_data_root / file["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(extraction / "artifacts" / file["path"], destination)
            if _sha(destination) != file["sha256"]:
                raise OSError("restored artifact checksum mismatch")
    return {"head_manifest_id": manifest["head_manifest_id"], "artifact_count": len(manifest["artifacts"]),
            "restore_data_root": str(destination_data_root)}
