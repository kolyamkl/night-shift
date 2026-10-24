// Pixel icons on a 12-pixel grid ("c" = currentColor) and 16-pixel document pictograms in the MuGuard palette.

export const ICONS = {
  plus: ["............", ".....cc.....", ".....cc.....", ".....cc.....", ".....cc.....", ".cccccccccc.", ".cccccccccc.", ".....cc.....", ".....cc.....", ".....cc.....", ".....cc.....", "............"],
  upload: [".....cc.....", "....cccc....", "...cccccc...", "..cc.cc.cc..", ".....cc.....", ".....cc.....", ".....cc.....", "............", "cc........cc", "cc........cc", "cccccccccccc", "cccccccccccc"],
  download: [".....cc.....", ".....cc.....", ".....cc.....", "..cc.cc.cc..", "...cccccc...", "....cccc....", ".....cc.....", "............", "cc........cc", "cc........cc", "cccccccccccc", "cccccccccccc"],
  file: ["ccccccc.....", "c.....cc....", "c.....c.c...", "c.....cccc..", "c........c..", "c.cccccc.c..", "c........c..", "c.cccccc.c..", "c........c..", "c.cccc...c..", "c........c..", "cccccccccc.."],
  clipboard: ["....cccc....", ".cccc..cccc.", ".c..cccc..c.", ".c........c.", ".c.cccccc.c.", ".c........c.", ".c.cccccc.c.", ".c........c.", ".c.cccc...c.", ".c........c.", ".c........c.", ".cccccccccc."],
  lock: ["...cccccc...", "..cc....cc..", "..c......c..", "..c......c..", "cccccccccccc", "cccccccccccc", "ccccc..ccccc", "ccccc..ccccc", "ccccc..ccccc", "cccccccccccc", "cccccccccccc", "............"],
  check: ["............", "..........cc", ".........ccc", "........ccc.", ".......ccc..", "cc....ccc...", "ccc..ccc....", ".ccccc......", "..ccc.......", "...c........", "............", "............"],
  close: ["cc........cc", "ccc......ccc", ".ccc....ccc.", "..ccc..ccc..", "...cccccc...", "....cccc....", "....cccc....", "...cccccc...", "..ccc..ccc..", ".ccc....ccc.", "ccc......ccc", "cc........cc"],
  right: ["............", "......c.....", "......cc....", "......ccc...", "cccccccccc..", "ccccccccccc.", "ccccccccccc.", "cccccccccc..", "......ccc...", "......cc....", "......c.....", "............"],
  up: ["............", "............", "............", ".....cc.....", "....cccc....", "...cc..cc...", "..cc....cc..", ".cc......cc.", "............", "............", "............", "............"],
  down: ["............", "............", "............", "............", ".cc......cc.", "..cc....cc..", "...cc..cc...", "....cccc....", ".....cc.....", "............", "............", "............"],
  eye: ["............", "............", "...cccccc...", ".cc......cc.", "c....cc....c", "c...cccc...c", "c...cccc...c", "c....cc....c", ".cc......cc.", "...cccccc...", "............", "............"],
  marker: ["........ccc.", ".......ccccc", "......ccccc.", ".....ccccc..", "....ccccc...", "...ccccc....", "..ccccc.....", "..cccc......", ".cc.c.......", ".ccc........", "cccc........", "............"],
} as const;

export type IconName = keyof typeof ICONS;

// Document pictograms for sample cards (k ink, r signal, w paper, g stone).
export const PICTOGRAMS: Record<string, readonly string[]> = {
  tenancy: [
    "................", ".......kk.......", "......krrk......", ".....krrrrk.....", "....krrrrrrk....", "...krrrrrrrrk...",
    "..krrrrrrrrrrk..", ".kkkkkkkkkkkkkk.", "..kwwwwwwwwwwk..", "..kwkkwwwwkkwk..", "..kwkkwwwwkkwk..",
    "..kwwwwkkwwwwk..", "..kwwwwkkwwwwk..", "..kwwwwkkwwwwk..", "..kkkkkkkkkkkk..", "................",
  ],
  employment: [
    "................", "................", "......kkkk......", ".....k....k.....", ".kkkkkkkkkkkkkk.", ".kggggggggggggk.",
    ".kggggggggggggk.", ".kggggggggggggk.", ".kkkkkkrrkkkkkk.", ".kggggkrrkggggk.", ".kggggggggggggk.",
    ".kggggggggggggk.", ".kggggggggggggk.", ".kkkkkkkkkkkkkk.", "................", "................",
  ],
  nda: [
    "................", ".....kkkkkk.....", "....krrrrrrk....", "...krrrrrrrrk...", "..krrrrwwrrrrk..", "..krrrwwwwrrrk..",
    "..krrrwwwwrrrk..", "..krrrrwwrrrrk..", "..krrrrwwrrrrk..", "..krrrwwwwrrrk..", "...krrrrrrrrk...",
    "....krrrrrrk....", ".....kkkkkk.....", "....kk....kk....", "...kk......kk...", "................",
  ],
  service: [
    "................", ".......kk.......", "...kk.kkkk.kk...", "...kkkkggkkkk...", "....kggggggk....", "..kkkggkkggkkk..",
    ".kkggk....kggkk.", "..kggk....kggk..", "..kggk....kggk..", ".kkggk....kggkk.", "..kkkggkkggkkk..",
    "....kggggggk....", "...kkkkggkkkk...", "...kk.kkkk.kk...", ".......kk.......", "................",
  ],
  letter: [
    "................", "................", ".kkkkkkkkkkkkkk.", ".kwkwwwwwwwwkwk.", ".kwwkwwwwwwkwwk.", ".kwwwkwwwwkwwwk.",
    ".kwwwwkrrkwwwwk.", ".kwwwwkrrkwwwwk.", ".kwwwkwkkwkwwwk.", ".kwwkwwwwwwkwwk.", ".kwkwwwwwwwwkwk.",
    ".kkwwwwwwwwwwkk.", ".kkkkkkkkkkkkkk.", "................", "................", "................",
  ],
  receipt: [
    "................", "...kkkkkkkkkk...", "...kwwwwwwwwk...", "...kwkkkkkkwk...", "...kwwwwwwwwk...", "...kwkkkwrrwk...",
    "...kwwwwwwwwk...", "...kwkkkwrrwk...", "...kwwwwwwwwk...", "...kwkkkwrrwk...", "...kwwwwwwwwk...",
    "...kwkkkkkkwk...", "...kwwwwwwwwk...", "...kwwwwwwwwk...", "...k.k.k.k.kk...", "................",
  ],
  coin: [
    "................", "................", "....kkkkkkkk....", "...kggggggggk...", "...kkkkkkkkkk...", "...kggggggggk...",
    "...kkkkkkkkkk...", "...kggggggggk...", "...kkkkkkkkkk...", "...kggwwggggk...", "...kkkkkkkkkk...",
    "...kggggggggk...", "....kkkkkkkk....", "................", "................", "................",
  ],
  person: [
    "................", "......kkkk......", ".....kwwwwk.....", ".....kwwwwk.....", ".....kwwwwk.....", "......kkkk......",
    "................", "....kkkkkkkk....", "...krrrrrrrrk...", "...krrrrrrrrk...", "...krrrrrrrrk...",
    "...krrrrrrrrk...", "...kkkkkkkkkk...", "................", "................", "................",
  ],
  shield: [
    "................", "..kkkkkkkkkkkk..", "..kwwwwwwwwwwk..", "..kwwwwkkwwwwk..", "..kwwwkkkkwwwk..", "..kwwwkkkkwwwk..",
    "..kwwwwkkwwwwk..", "..kwwwwkkwwwwk..", "...kwwkkkkwwk...", "...kwwwwwwwwk...", "....kwwwwwwk....",
    ".....kwwwwk.....", "......kwwk......", ".......kk.......", "................", "................",
  ],
  heart: [
    "................", "................", "...kkk....kkk...", "..krrrk..krrrk..", ".krrrrrkkrrrrrk.", ".krrrrrrrrrrrrk.",
    ".krrrrrrrrrrrrk.", "..krrrrrrrrrrk..", "...krrrrrrrrk...", "....krrrrrrk....", ".....krrrrk.....",
    "......krrk......", ".......kk.......", "................", "................", "................",
  ],
  form: [
    "................", "......kkkk......", "...kkkkrrkkkk...", "...kwwkkkkwwk...", "...kwwwwwwwwk...", "...kwkkkkkkwk...",
    "...kwwwwwwwwk...", "...kwkkkkkwwk...", "...kwwwwwwwwk...", "...kwkkkkkkwk...", "...kwwwwwwwwk...",
    "...kwkkkwwwwk...", "...kwwwwwwwwk...", "...kkkkkkkkkk...", "................", "................",
  ],
  file: [
    "................", "..kkkkkkkkk.....", "..kwwwwwwwkk....", "..kwwwwwwwkwk...", "..kwwwwwwwkkkk..", "..kwwwwwwwwwwk..",
    "..kwkkkkkwwwwk..", "..kwwwwwwwwwwk..", "..kwkkkkkkkwwk..", "..kwwwwwwwwwwk..", "..kwrrrrwkkkwk..",
    "..kwwwwwwwwwwk..", "..kwkkkkkkwwwk..", "..kwwwwwwwwwwk..", "..kkkkkkkkkkkk..", "................",
  ],
};

const KINDS: [RegExp, keyof typeof PICTOGRAMS][] = [
  [/tenancy|lease/, "tenancy"],
  [/payslip|bank|statement/, "coin"],
  [/employ/, "employment"],
  [/nda|confidential/, "nda"],
  [/service/, "service"],
  [/invoice|bill|receipt/, "receipt"],
  [/insurance|claim/, "shield"],
  [/medical|health|gp/, "heart"],
  [/\bcv\b|_cv|resume/, "person"],
  [/hr_|form/, "form"],
  [/letter|email|eml|gov/, "letter"],
];

export function pictogramFor(name: string): readonly string[] {
  const n = name.toLowerCase();
  const hit = KINDS.find(([re]) => re.test(n));
  return PICTOGRAMS[hit ? hit[1] : "file"];
}
