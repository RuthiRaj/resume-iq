"use client";

import React, { useState } from "react";
import { useCareer } from "@/lib/store";
import { DocumentData } from "@/lib/validations";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Modal } from "@/components/ui/modal";
import { EmptyState } from "@/components/common/state-views";
import { formatDate } from "@/lib/utils";
import {
  Files,
  UploadCloud,
  FileText,
  Trash2,
  Eye,
  CheckCircle2,
  Sparkles,
  Loader2,
  AlertCircle,
  FileCheck,
} from "lucide-react";

export default function DocumentsPage() {
  const { documents, addDocument, deleteDocument } = useCareer();
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState<DocumentData | null>(null);

  // Upload simulator states
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [docType, setDocType] = useState<DocumentData["type"]>("Resume");
  const [isSimulatingParse, setIsSimulatingParse] = useState(false);
  const [parseProgress, setParseProgress] = useState(0);
  const [parseMessage, setParseMessage] = useState("");
  const [uploadError, setUploadError] = useState<string | null>(null);

  const handleSimulatedUpload = () => {
    if (!uploadFile) {
      setUploadError("Please select a document file (.pdf, .docx, .doc, or .txt) to upload.");
      return;
    }

    setUploadError(null);
    setIsSimulatingParse(true);
    setParseProgress(20);
    setParseMessage("Reading document binary structure...");

    setTimeout(() => {
      setParseProgress(55);
      setParseMessage("Extracting entities: Experience, Education, and Skills...");
    }, 800);

    setTimeout(() => {
      setParseProgress(85);
      setParseMessage("Normalizing taxonomy against Career Workspace schema...");
    }, 1600);

    setTimeout(async () => {
      try {
        setParseProgress(100);
        setParseMessage("Document uploaded and parsed successfully!");

        const fileName = uploadFile.name;
        await addDocument(
          {
            name: fileName,
            type: docType,
            fileSize: `${(uploadFile.size / 1024).toFixed(0)} KB`,
            uploadDate: new Date().toISOString().split("T")[0],
            parsedStatus: "Parsed",
            content: `Extracted text from ${fileName}: Verified credentials, coursework, projects, and work history indexed into master workspace.`,
          },
          uploadFile
        );

        setIsSimulatingParse(false);
        setUploadFile(null);
        setIsUploadOpen(false);
        setParseProgress(0);
      } catch (err: any) {
        setUploadError(err.message || "Failed to upload document.");
        setIsSimulatingParse(false);
        setParseProgress(0);
      }
    }, 2400);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-h2 font-semibold text-primary">Original Documents & Transcripts</h2>
          <p className="text-small text-secondary">
            Upload raw PDF resumes, official transcripts, and certificates for automated AI extraction.
          </p>
        </div>
        <Button onClick={() => setIsUploadOpen(true)} variant="primary" size="sm" className="gap-1.5 self-start">
          <UploadCloud className="h-4 w-4" />
          <span>Upload Document</span>
        </Button>
      </div>

      {documents.length === 0 ? (
        <EmptyState
          title="No documents uploaded"
          description="Upload an existing resume or academic transcript PDF to automatically populate your workspace."
          actionLabel="Upload Document"
          onAction={() => setIsUploadOpen(true)}
          icon={Files}
        />
      ) : (
        <div className="space-y-3">
          {documents.map((doc) => (
            <Card key={doc.id} className="hover:border-accent/30 transition-all">
              <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[6px] bg-accent-soft text-accent">
                    <FileText className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-body font-semibold text-primary">{doc.name}</h4>
                      <Badge variant="outline">{doc.type}</Badge>
                      <Badge
                        variant={
                          doc.parsedStatus === "Parsed"
                            ? "success"
                            : doc.parsedStatus === "Processing"
                            ? "warning"
                            : "default"
                        }
                      >
                        {doc.parsedStatus}
                      </Badge>
                    </div>
                    <div className="mt-1 flex items-center gap-3 text-small text-muted">
                      <span>Size: {doc.fileSize}</span>
                      <span>&bull;</span>
                      <span>Uploaded {formatDate(doc.uploadDate)}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 self-start sm:self-center">
                  <Button
                    onClick={() => setSelectedDoc(doc)}
                    variant="outline"
                    size="sm"
                    className="gap-1.5"
                  >
                    <Eye className="h-3.5 w-3.5" />
                    <span>Preview & Parse</span>
                  </Button>
                  <Button
                    onClick={() => doc.id && deleteDocument(doc.id)}
                    variant="ghost"
                    size="sm"
                    className="text-status-error hover:bg-status-error-soft"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Upload Modal */}
      <Modal
        isOpen={isUploadOpen}
        onClose={() => !isSimulatingParse && setIsUploadOpen(false)}
        title="Upload Career Document"
        description="Select a PDF file to parse into your career workspace."
        maxWidth="lg"
      >
        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Document Type</label>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value as DocumentData["type"])}
              className="flex h-9 w-full rounded-input border border-border bg-surface px-3 py-1.5 text-body text-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent"
            >
              <option value="Resume">Resume / CV</option>
              <option value="Transcript">Official Academic Transcript</option>
              <option value="Certificate">Certificate of Completion</option>
              <option value="Recommendation">Letter of Recommendation</option>
              <option value="Other">Other Document</option>
            </select>
          </div>

          {/* Drag & drop simulated box */}
          <div
            className="flex flex-col items-center justify-center rounded-card border-2 border-dashed border-border bg-page p-8 text-center hover:border-accent/40 cursor-pointer transition-colors"
            onClick={() => document.getElementById("file-input")?.click()}
          >
            <UploadCloud className="h-8 w-8 text-accent mb-2" />
            <p className="text-body font-medium text-primary">
              {uploadFile ? uploadFile.name : "Click to select or drop PDF here"}
            </p>
            <p className="text-small text-muted mt-1">Supports PDF, DOCX up to 15MB</p>
            <input
              id="file-input"
              type="file"
              accept=".pdf,.doc,.docx"
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  setUploadFile(e.target.files[0]);
                }
              }}
            />
          </div>

          {uploadError && (
            <div className="rounded-btn border border-status-error/30 bg-status-error-soft p-3 text-status-error text-small">
              {uploadError}
            </div>
          )}

          {/* Parse Simulation Bar */}
          {isSimulatingParse && (
            <div className="space-y-2 rounded-btn border border-accent/20 bg-accent-soft p-4">
              <div className="flex items-center justify-between text-small font-medium text-accent">
                <div className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>{parseMessage}</span>
                </div>
                <span>{parseProgress}%</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-border">
                <div
                  className="h-full bg-accent transition-all duration-300"
                  style={{ width: `${parseProgress}%` }}
                />
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2.5 pt-4 border-t border-border/60">
            <Button
              type="button"
              variant="ghost"
              disabled={isSimulatingParse}
              onClick={() => {
                setIsUploadOpen(false);
                setUploadError(null);
              }}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="primary"
              disabled={isSimulatingParse || !uploadFile}
              onClick={handleSimulatedUpload}
              className="gap-1.5"
            >
              <Sparkles className="h-4 w-4" />
              <span>{isSimulatingParse ? "Parsing..." : "Upload & Parse Document"}</span>
            </Button>
          </div>
        </div>
      </Modal>

      {/* Document Inspection & Parse Modal */}
      {selectedDoc && (
        <Modal
          isOpen={true}
          onClose={() => setSelectedDoc(null)}
          title={`Document: ${selectedDoc.name}`}
          description={`Uploaded on ${selectedDoc.uploadDate} • Status: ${selectedDoc.parsedStatus}`}
          maxWidth="3xl"
        >
          <div className="space-y-4">
            {/* Visual document preview */}
            <div className="rounded-btn border border-border bg-page p-6 font-mono text-small text-secondary space-y-3">
              <div className="flex items-center justify-between border-b border-border pb-3 text-primary font-semibold">
                <span>DOCUMENT PREVIEW & EXTRACTION BUFFER</span>
                <Badge variant="success">Parsed 100%</Badge>
              </div>

              <div className="space-y-2 text-primary">
                <p className="font-semibold text-body">{selectedDoc.name}</p>
                <p className="text-secondary">
                  Type: {selectedDoc.type} • Size: {selectedDoc.fileSize}
                </p>
                <div className="text-secondary whitespace-pre-wrap pt-2 font-sans text-small leading-relaxed">
                  {selectedDoc.content || "Document parsed and indexed into master workspace."}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between rounded-btn border border-status-success/30 bg-status-success-soft p-3 text-status-success text-small">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4" />
                <span>All entities from this document are synchronized with your active Workspace.</span>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button onClick={() => setSelectedDoc(null)} variant="primary">
                Close Preview
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
