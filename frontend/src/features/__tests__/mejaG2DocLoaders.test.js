// Meja gelombang 2 · Tugas 3 (R6) — isi pratinjau tidak boleh mengimpor registri: urutan impor tak boleh berpengaruh.
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: jest.fn(), defaults: { headers: { common: {} } } },
  API: "/api",
}));

test("ContraBonPreview diimpor SEBELUM registri: Body kontrabon tetap terdefinisi", () => {
  jest.isolateModules(() => {
    const Body = require("../documents/preview/bodies/ContraBonPreview").default;
    const { DOC_PREVIEWS } = require("../documents/preview/docPreviewRegistry");
    expect(typeof Body).toBe("function");
    expect(DOC_PREVIEWS.contra_bon.Body).toBeDefined();
    expect(DOC_PREVIEWS.contra_bon.Body).toBe(Body);
  });
});

test("registri tetap mengekspor loadDoc; docLoaders tidak mengimpor Body maupun registri", () => {
  const fs = require("fs");
  const path = require("path");
  const { loadDoc } = require("../documents/preview/docPreviewRegistry");
  expect(typeof loadDoc).toBe("function");
  const dir = path.join(__dirname, "..", "documents", "preview");
  const loaders = fs.readFileSync(path.join(dir, "docLoaders.js"), "utf8");
  expect(/from\s+["'][^"']*(bodies\/|docPreviewRegistry)/.test(loaders)).toBe(false);
  fs.readdirSync(path.join(dir, "bodies")).forEach((n) => {
    expect([n, /docPreviewRegistry/.test(fs.readFileSync(path.join(dir, "bodies", n), "utf8"))]).toEqual([n, false]);
  });
});
