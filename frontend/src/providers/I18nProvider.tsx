"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import enIn from "../i18n/en-IN.json";
import hiIn from "../i18n/hi-IN.json";

export type SupportedLocale =
  | "en-IN"
  | "hi-IN"
  | "mr-IN"
  | "bn-IN"
  | "ta-IN"
  | "te-IN"
  | "kn-IN"
  | "gu-IN";

export interface LocaleInfo {
  code: SupportedLocale;
  name: string;
  nativeName: string;
}

export const SUPPORTED_LOCALES: LocaleInfo[] = [
  { code: "en-IN", name: "English", nativeName: "English" },
  { code: "hi-IN", name: "Hindi", nativeName: "हिंदी" },
  { code: "mr-IN", name: "Marathi", nativeName: "मराठी" },
  { code: "bn-IN", name: "Bengali", nativeName: "বাংলা" },
  { code: "ta-IN", name: "Tamil", nativeName: "தமிழ்" },
  { code: "te-IN", name: "Telugu", nativeName: "తెలుగు" },
  { code: "kn-IN", name: "Kannada", nativeName: "ಕನ್ನಡ" },
  { code: "gu-IN", name: "Gujarati", nativeName: "ગુજરાતી" },
];

interface I18nContextType {
  locale: SupportedLocale;
  setLocale: (locale: SupportedLocale) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

const dictionaries: Record<string, Record<string, unknown>> = {
  "en-IN": enIn as Record<string, unknown>,
  "hi-IN": hiIn as Record<string, unknown>,
};

const I18nContext = createContext<I18nContextType>({
  locale: "en-IN",
  setLocale: () => {},
  t: (key: string) => key,
});

export const I18nProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [locale, setLocaleState] = useState<SupportedLocale>("en-IN");

  useEffect(() => {
    const saved = localStorage.getItem("lcc_locale") as SupportedLocale;
    if (saved && SUPPORTED_LOCALES.some((l) => l.code === saved)) {
      setLocaleState(saved);
    }
  }, []);

  const setLocale = (newLocale: SupportedLocale) => {
    setLocaleState(newLocale);
    localStorage.setItem("lcc_locale", newLocale);
  };

  const t = (path: string, params?: Record<string, string | number>): string => {
    const dict = dictionaries[locale] || dictionaries["en-IN"];
    const fallback = dictionaries["en-IN"];

    const resolve = (obj: any, p: string) => {
      return p.split(".").reduce((prev, curr) => (prev && prev[curr] !== undefined ? prev[curr] : null), obj);
    };

    let val = resolve(dict, path) || resolve(fallback, path) || path;
    if (typeof val === "string" && params) {
      Object.entries(params).forEach(([k, v]) => {
        val = val.replace(`{${k}}`, String(v));
      });
    }
    return typeof val === "string" ? val : path;
  };

  return (
    <I18nContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </I18nContext.Provider>
  );
};

export const useI18n = () => useContext(I18nContext);
