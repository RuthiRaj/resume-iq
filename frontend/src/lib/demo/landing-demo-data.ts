/**
 * Dedicated Static Fictional Demo Dataset for Public Landing Page
 * 
 * ARCHITECTURAL NOTICE:
 * This dataset is strictly for unauthenticated public preview.
 * It contains ZERO Firebase SDK calls, ZERO database hooks, and NO real user identifiers.
 */

export interface DemoProfile {
  name: string;
  role: string;
  headline: string;
  location: string;
}

export interface DemoCareerSignal {
  overall: number;
  breakdown: Array<{
    name: string;
    score: number;
    color: string;
    key: string;
  }>;
}

export const landingDemoProfile: DemoProfile = {
  name: "Alex Rivera",
  role: "Senior Product Systems Designer",
  headline: "Alex Rivera — Senior Product Systems Designer",
  location: "San Francisco, CA",
};

export const landingDemoSignalData: DemoCareerSignal = {
  overall: 93,
  breakdown: [
    { name: "Profile", score: 100, color: "#3652D9", key: "profile" },
    { name: "Education", score: 95, color: "#12805C", key: "education" },
    { name: "Skills", score: 92, color: "#B54708", key: "skills" },
    { name: "Projects", score: 96, color: "#7A5AF8", key: "projects" },
    { name: "Experience", score: 90, color: "#0086C9", key: "experience" },
    { name: "Certifications", score: 85, color: "#E04F16", key: "certifications" },
  ],
};
