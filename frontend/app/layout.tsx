import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Kagaz — Document Intelligence & Verification",
  description: "Archival manuscript document intelligence, classification, and verification platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
