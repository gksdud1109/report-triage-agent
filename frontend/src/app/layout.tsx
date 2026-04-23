import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Report Triage",
  description: "운영 큐 브라우저 (MVP)",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko">
      <body
        style={{
          margin: 0,
          fontFamily:
            "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          background: "#f7f7f8",
          color: "#1f2328",
        }}
      >
        {children}
      </body>
    </html>
  );
}
