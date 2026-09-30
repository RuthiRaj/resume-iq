/**
 * Ambient module declaration for pdfjs-dist ESM build.
 * Required because the E2E specs import pdfjs-dist/build/pdf.mjs
 * for PDF text extraction and the package ships no .d.ts for that path.
 */
declare module "pdfjs-dist/build/pdf.mjs" {
  export function getDocument(params: {
    data: Uint8Array;
  }): { promise: Promise<PDFDocumentProxy> };

  interface PDFDocumentProxy {
    numPages: number;
    getPage(pageNumber: number): Promise<PDFPageProxy>;
  }

  interface PDFPageProxy {
    getTextContent(): Promise<TextContent>;
  }

  interface TextContent {
    items: Array<{ str: string }>;
  }
}
