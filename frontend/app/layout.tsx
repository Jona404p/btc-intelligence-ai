import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "BTC Intelligence AI | Market Research",
  description: "Plataforma profesional de inteligencia de mercado y research de trading para Bitcoin.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
