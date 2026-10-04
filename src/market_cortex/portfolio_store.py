"""Auditable local portfolio versions; never synchronizes or writes to a broker."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from psycopg.conninfo import conninfo_to_dict

from .database import connect
from .risk_contracts import Portfolio, PortfolioCreate, PositionChange


class PortfolioStore:
    def __init__(self, dsn: str, environment: str):
        self.dsn = dsn
        self.environment = environment

    def create(self, request: PortfolioCreate) -> Portfolio:
        if request.classification == "SYNTHETIC_TEST_PORTFOLIO" and (
                self.environment != "PILOT_TEST" or not
                conninfo_to_dict(self.dsn).get("dbname", "").lower().endswith("_test")):
            raise ValueError("SYNTHETIC_PORTFOLIO_REQUIRES_TEST_DATABASE")
        now = datetime.now(timezone.utc)
        result = Portfolio(portfolio_id=uuid4(), name=request.name,
            base_currency=request.base_currency, capital=request.capital,
            classification=request.classification, version=1, created_at=now,
            updated_at=now, positions=[])
        with connect(self.dsn) as connection:
            connection.execute("""INSERT INTO portfolios
                (portfolio_id,name,base_currency,capital,current_version,created_at)
                VALUES (%s,%s,%s,%s,1,%s)""",
                (result.portfolio_id, result.name, result.base_currency,
                 result.capital, now))
            self._append(connection, result, "created", "PORTFOLIO_CREATED")
        return result

    @staticmethod
    def _append(connection, portfolio: Portfolio, action: str, reason: str) -> None:
        connection.execute("""INSERT INTO portfolio_versions
            (portfolio_id,version,action,reason,payload) VALUES (%s,%s,%s,%s,%s)""",
            (portfolio.portfolio_id, portfolio.version, action, reason,
             json.dumps(portfolio.model_dump(mode="json"))))

    def get(self, portfolio_id: UUID, version: int | None = None) -> Portfolio | None:
        with connect(self.dsn) as connection:
            row = connection.execute("""SELECT v.payload FROM portfolios p
                JOIN portfolio_versions v ON v.portfolio_id=p.portfolio_id
                    AND v.version=COALESCE(%s,p.current_version)
                WHERE p.portfolio_id=%s""", (version, portfolio_id)).fetchone()
        return Portfolio.model_validate(row[0]) if row else None

    def list(self, limit: int = 50) -> list[Portfolio]:
        with connect(self.dsn) as connection:
            rows = connection.execute("""SELECT v.payload FROM portfolios p
                JOIN portfolio_versions v ON v.portfolio_id=p.portfolio_id
                    AND v.version=p.current_version ORDER BY p.created_at DESC LIMIT %s""",
                (limit,)).fetchall()
        return [Portfolio.model_validate(row[0]) for row in rows]

    def versions(self, portfolio_id: UUID) -> list[dict]:
        with connect(self.dsn) as connection:
            rows = connection.execute("""SELECT version,recorded_at,action,reason FROM portfolio_versions
                WHERE portfolio_id=%s ORDER BY version""", (portfolio_id,)).fetchall()
        return [{"version": row[0], "recorded_at": row[1].isoformat(),
                 "action": row[2], "reason": row[3]} for row in rows]

    def change(self, portfolio_id: UUID, request: PositionChange) -> Portfolio:
        with connect(self.dsn) as connection:
            head = connection.execute("SELECT current_version FROM portfolios WHERE portfolio_id=%s FOR UPDATE",
                                      (portfolio_id,)).fetchone()
            if head is None:
                raise LookupError("PORTFOLIO_NOT_FOUND")
            row = connection.execute("""SELECT payload FROM portfolio_versions
                WHERE portfolio_id=%s AND version=%s""", (portfolio_id, head[0])).fetchone()
            previous = Portfolio.model_validate(row[0])
            positions = list(previous.positions)
            index = next((i for i, position in enumerate(positions)
                          if position.position_id == request.position.position_id), None)
            if request.action == "add":
                if index is not None or request.position.closed_at is not None:
                    raise ValueError("POSITION_ALREADY_EXISTS_OR_CLOSED")
                positions.append(request.position)
            else:
                if index is None or positions[index].closed_at is not None:
                    raise ValueError("OPEN_POSITION_NOT_FOUND")
                old = positions[index]
                if (old.instrument_id != request.position.instrument_id or
                        old.native_currency != request.position.native_currency or
                        old.opened_at != request.position.opened_at):
                    raise ValueError("POSITION_IDENTITY_IMMUTABLE")
                if request.action == "close" and request.position.closed_at is None:
                    raise ValueError("CLOSE_TIMESTAMP_REQUIRED")
                if request.action == "update" and request.position.closed_at is not None:
                    raise ValueError("UPDATE_CANNOT_CLOSE_POSITION")
                positions[index] = request.position
            updated = previous.model_copy(update={"version": previous.version+1,
                "updated_at": datetime.now(timezone.utc), "positions": positions})
            self._append(connection, updated,
                         {"add": "position_added", "update": "position_updated",
                          "close": "position_closed"}[request.action], request.reason)
            connection.execute("UPDATE portfolios SET current_version=%s WHERE portfolio_id=%s",
                               (updated.version, portfolio_id))
        return updated

    def save_risk(self, risk: dict) -> None:
        with connect(self.dsn) as connection:
            connection.execute("""INSERT INTO portfolio_risk_snapshots
                (snapshot_id,portfolio_id,portfolio_version,manifest_id,as_of,calculation_version,payload)
                VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (snapshot_id) DO NOTHING""",
                (risk["snapshot_id"], risk["portfolio_id"], risk["portfolio_version"],
                 risk["source_manifest_id"], risk["as_of"], risk["calculation_version"],
                 json.dumps(risk, default=str)))

    def risk_snapshot(self, snapshot_id: UUID) -> dict | None:
        with connect(self.dsn) as connection:
            row = connection.execute("SELECT payload FROM portfolio_risk_snapshots WHERE snapshot_id=%s",
                                     (snapshot_id,)).fetchone()
        return row[0] if row else None
