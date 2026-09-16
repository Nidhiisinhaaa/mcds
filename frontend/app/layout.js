import {
  Source_Serif_4,
  Noto_Sans,
  Noto_Sans_Devanagari,
  Noto_Sans_Tamil,
  Noto_Sans_Telugu,
  Noto_Sans_Bengali,
  Noto_Sans_Kannada,
  Noto_Sans_Gujarati,
  Noto_Sans_Malayalam,
} from "next/font/google";
import "./globals.css";

const sourceSerif = Source_Serif_4({
  variable: "--font-heading",
  subsets: ["latin"],
  weight: ["600", "700"],
});

const notoSans = Noto_Sans({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const notoSansDevanagari = Noto_Sans_Devanagari({
  variable: "--font-devanagari",
  subsets: ["devanagari"],
  weight: ["400", "500", "600"],
});

const notoSansTamil = Noto_Sans_Tamil({
  variable: "--font-tamil",
  subsets: ["tamil"],
  weight: ["400", "500", "600"],
});

const notoSansTelugu = Noto_Sans_Telugu({
  variable: "--font-telugu",
  subsets: ["telugu"],
  weight: ["400", "500", "600"],
});

const notoSansBengali = Noto_Sans_Bengali({
  variable: "--font-bengali",
  subsets: ["bengali"],
  weight: ["400", "500", "600"],
});

const notoSansKannada = Noto_Sans_Kannada({
  variable: "--font-kannada",
  subsets: ["kannada"],
  weight: ["400", "500", "600"],
});

const notoSansGujarati = Noto_Sans_Gujarati({
  variable: "--font-gujarati",
  subsets: ["gujarati"],
  weight: ["400", "500", "600"],
});

const notoSansMalayalam = Noto_Sans_Malayalam({
  variable: "--font-malayalam",
  subsets: ["malayalam"],
  weight: ["400", "500", "600"],
});

export const metadata = {
  title: "Bedside | Lifestyle Assessment",
  description:
    "A multilingual clinical dialogue system that helps patients describe their symptoms and lifestyle before seeing the doctor.",
};

export default function RootLayout({ children }) {
  const fontVariables = [
    sourceSerif.variable,
    notoSans.variable,
    notoSansDevanagari.variable,
    notoSansTamil.variable,
    notoSansTelugu.variable,
    notoSansBengali.variable,
    notoSansKannada.variable,
    notoSansGujarati.variable,
    notoSansMalayalam.variable,
  ].join(" ");

  return (
    <html lang="en" className={`${fontVariables} h-full`}>
      <body className="min-h-full flex flex-col bg-page text-ink font-body antialiased">
        {children}
      </body>
    </html>
  );
}
