import { GoogleGenAI } from "@google/genai";
import { AiAnalyzerProvider, AiAnalysisRequest } from "./provider";
import { AiAnalysisResult, AiAnalysisResultSchema } from "./schemas";

export class GeminiAnalyzerProvider implements AiAnalyzerProvider {
  readonly name = "gemini";

  async analyze(request: AiAnalysisRequest): Promise<AiAnalysisResult> {
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey || apiKey.trim() === "" || apiKey === "your_server_side_gemini_api_key_here") {
      const error = new Error("GEMINI_API_KEY is not configured on the server.");
      (error as any).statusCode = 503;
      throw error;
    }

    const modelName = process.env.AI_ANALYZER_MODEL || "gemini-2.5-flash";

    const ai = new GoogleGenAI({ apiKey });

    const prompt = `You are a Senior Principal Technical Recruiter and ATS (Applicant Tracking System) Evaluation Engine.
Your task is to analyze the candidate's resume evidence against the provided Job Description for the target role: "${request.targetRole}"${
      request.targetCompany ? ` at ${request.targetCompany}` : ""
    }.

CRITICAL EVIDENCE RULES (STRICT NON-NEGOTIABLE CONSTRAINT):
1. Evaluate ONLY the evidence explicitly contained in the supplied Resume Evidence below.
2. DO NOT hallucinate, assume, or invent candidate experience, skills, achievements, metrics, or technologies.
3. If a requirement in the Job Description has NO supporting evidence in the resume, you MUST classify it as a missing skill or gap with High or Medium priority.
4. If a requirement is partially mentioned or adjacent, classify it as a partial match with actionable advice.
5. Scores must reflect genuine semantic congruence (0 to 100).
6. Return only valid JSON conforming to the requested schema.

TARGET JOB TITLE: ${request.targetRole}
${request.targetCompany ? `TARGET COMPANY: ${request.targetCompany}` : ""}

TARGET JOB DESCRIPTION:
"""
${request.jobDescription}
"""

CANDIDATE RESUME EVIDENCE:
"""
${JSON.stringify(request.candidateEvidence, null, 2)}
"""

Evaluate the candidate now and return the structured ATS assessment.`;

    const geminiSchema = {
      type: "OBJECT",
      properties: {
        atsScore: {
          type: "INTEGER",
          description: "Overall ATS readiness score between 0 and 100",
        },
        scoreBreakdown: {
          type: "OBJECT",
          properties: {
            relevance: { type: "INTEGER", description: "Role and domain relevance score 0-100" },
            keywords: { type: "INTEGER", description: "Keyword density match score 0-100" },
            metrics: { type: "INTEGER", description: "Quantifiable metrics and impact score 0-100" },
            formatting: { type: "INTEGER", description: "Structure and clarity score 0-100" },
          },
          required: ["relevance", "keywords", "metrics", "formatting"],
        },
        summaryFeedback: {
          type: "STRING",
          description: "2-3 clear sentences summarizing candidate fit and primary areas of improvement",
        },
        matchingSkills: {
          type: "ARRAY",
          items: {
            type: "OBJECT",
            properties: {
              name: { type: "STRING" },
              context: { type: "STRING", description: "Specific section/bullet where this requirement was evidenced" },
            },
            required: ["name", "context"],
          },
        },
        missingSkills: {
          type: "ARRAY",
          items: {
            type: "OBJECT",
            properties: {
              name: { type: "STRING" },
              priority: { type: "STRING", enum: ["High", "Medium", "Low"] },
              reason: { type: "STRING", description: "Why this requirement from the JD is missing in candidate evidence" },
            },
            required: ["name", "priority", "reason"],
          },
        },
        partialSkills: {
          type: "ARRAY",
          items: {
            type: "OBJECT",
            properties: {
              name: { type: "STRING" },
              note: { type: "STRING", description: "How the candidate can emphasize adjacent evidence" },
            },
            required: ["name", "note"],
          },
        },
      },
      required: [
        "atsScore",
        "scoreBreakdown",
        "summaryFeedback",
        "matchingSkills",
        "missingSkills",
        "partialSkills",
      ],
    };

    let responseText = "";
    try {
      const response = await ai.models.generateContent({
        model: modelName,
        contents: prompt,
        config: {
          responseMimeType: "application/json",
          responseSchema: geminiSchema as any,
          temperature: 0.2,
        },
      });

      responseText = response.text || "";
    } catch (err: any) {
      // Handle rate limit and quota issues gracefully
      const errMessage = err?.message || String(err);
      if (errMessage.includes("429") || errMessage.toLowerCase().includes("quota") || errMessage.toLowerCase().includes("rate limit")) {
        const rateLimitError = new Error("AI provider rate limit reached. Please wait a moment before analyzing again.");
        (rateLimitError as any).statusCode = 429;
        throw rateLimitError;
      }
      if (errMessage.includes("API key not valid") || errMessage.includes("API_KEY_INVALID")) {
        const authError = new Error("Invalid Gemini API key configured on server.");
        (authError as any).statusCode = 503;
        throw authError;
      }
      const upstreamError = new Error("AI analysis service encountered an error processing the request.");
      (upstreamError as any).statusCode = 503;
      throw upstreamError;
    }

    if (!responseText) {
      const emptyError = new Error("AI provider returned an empty response.");
      (emptyError as any).statusCode = 503;
      throw emptyError;
    }

    let parsedJson: any;
    try {
      parsedJson = JSON.parse(responseText);
    } catch (parseErr) {
      const invalidJsonError = new Error("AI provider returned invalid JSON format.");
      (invalidJsonError as any).statusCode = 500;
      throw invalidJsonError;
    }

    // Attach metadata
    const resultWithMetadata = {
      ...parsedJson,
      metadata: {
        provider: this.name,
        model: modelName,
        analyzedAt: new Date().toISOString(),
        jobDescriptionHash: request.jobDescriptionHash,
        targetRole: request.targetRole,
        targetCompany: request.targetCompany,
      },
    };

    // Strict Zod validation
    const validation = AiAnalysisResultSchema.safeParse(resultWithMetadata);
    if (!validation.success) {
      const validationError = new Error(`AI response failed schema validation: ${validation.error.message}`);
      (validationError as any).statusCode = 500;
      throw validationError;
    }

    return validation.data;
  }
}
