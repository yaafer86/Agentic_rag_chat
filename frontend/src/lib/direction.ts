// RTL script detection based on Unicode ranges.
// We look at the first "strong" character in the text; ASCII/Latin yields LTR,
// Arabic/Hebrew/Syriac/Thaana/Persian/N'Ko/Samaritan all yield RTL.
// This is lightweight and does not require the Intl.Locale API which varies by browser.

const RTL_RANGES: Array<[number, number]> = [
  [0x0590, 0x05ff], // Hebrew
  [0x0600, 0x06ff], // Arabic (incl. Persian/Urdu base)
  [0x0700, 0x074f], // Syriac
  [0x0780, 0x07bf], // Thaana
  [0x07c0, 0x07ff], // N'Ko
  [0x0800, 0x083f], // Samaritan
  [0x0840, 0x085f], // Mandaic
  [0x08a0, 0x08ff], // Arabic Extended-A
  [0xfb1d, 0xfdff], // Hebrew + Arabic Presentation Forms-A
  [0xfe70, 0xfeff], // Arabic Presentation Forms-B
];

export type Direction = "ltr" | "rtl";

export function detectDirection(text: string): Direction {
  for (const ch of text) {
    const code = ch.codePointAt(0);
    if (code === undefined) continue;
    // Skip whitespace, digits, punctuation (below 0x0041 is mostly weak/neutral).
    if (code < 0x0041) continue;
    for (const [lo, hi] of RTL_RANGES) {
      if (code >= lo && code <= hi) return "rtl";
    }
    // Anything else that's strong → treat as LTR.
    return "ltr";
  }
  return "ltr";
}
