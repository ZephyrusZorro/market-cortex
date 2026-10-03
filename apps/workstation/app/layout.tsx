import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'MARKET CORTEX — Research Workstation',
  description: 'Private, local market intelligence workstation'
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
