export interface MockStep {
  step_number: number;
  action: string;
  field_name: string;
  value?: string;
  reasoning: string;
  confidence: number;
  x: number;
  y: number;
  timestamp: string;
  screenshot_url?: string;
  success: boolean;
  error?: string;
}

export interface RiskFlag {
  id: string;
  severity: "warning" | "info";
  message: string;
}

export interface MockApp {
  id: string;
  company: string;
  title: string;
  url: string;
  ats_type: string;
  salary: string | null;
  location: string;
  fit_score: number;
  status: string;
  created_at: string;
  submitted_at: string | null;
  keywords: string[];
  matched_keywords: string[];
  cover_letter: string;
  bullets: string[];
  risk_flags: RiskFlag[];
  steps: MockStep[];
}

const now = new Date();
const h = (n: number) => new Date(now.getTime() - n * 3_600_000).toISOString();

export const MOCK_APPLICATIONS: MockApp[] = [
  {
    id: "mock-001",
    company: "Anthropic",
    title: "Senior Software Engineer, Infrastructure",
    url: "boards.greenhouse.io/anthropic/jobs/4023991",
    ats_type: "greenhouse",
    salary: "$200k – $280k",
    location: "San Francisco, CA",
    fit_score: 87,
    status: "review",
    created_at: h(2),
    submitted_at: null,
    keywords: ["Python", "Kubernetes", "Distributed Systems", "FastAPI", "AWS", "Terraform", "Postgres", "Redis"],
    matched_keywords: ["Python", "FastAPI", "Postgres", "Redis", "AWS", "Kubernetes"],
    cover_letter: `Dear Hiring Manager,

I'm excited to apply for the Senior Software Engineer, Infrastructure role at Anthropic. With five years building high-throughput distributed systems in Python and extensive experience with Kubernetes orchestration at scale, I'm well-positioned to contribute to the infrastructure underpinning frontier AI research.

At my current role, I designed and shipped a FastAPI-based job orchestration platform handling 50k+ requests per day with sub-100ms p99 latency, backed by PostgreSQL and Redis. I've led Kubernetes migrations for services with zero-downtime SLA requirements, and maintained Terraform-managed AWS infrastructure across production and staging environments.

What draws me to Anthropic specifically is the intersection of engineering rigor and meaningful impact. I'd welcome the opportunity to bring that same rigor to systems that matter.

Best,
Kabiru Gacheru`,
    bullets: [
      "Designed and shipped a FastAPI-based job orchestration platform processing 50k+ daily requests at sub-100ms p99 latency across distributed Kubernetes clusters",
      "Led zero-downtime Kubernetes migration for 12 production services, reducing infrastructure costs 34% through right-sizing and spot instance adoption",
      "Built event-driven data pipelines on AWS using SQS, Lambda, and RDS Postgres — processing 2TB/day for real-time analytics",
      "Maintained Terraform modules for multi-region AWS infrastructure supporting 99.99% availability SLA across 8 services",
      "Mentored 3 engineers on distributed systems patterns; authored internal runbooks adopted org-wide",
    ],
    risk_flags: [
      {
        id: "rf-001",
        severity: "warning",
        message: "Cover letter references 'frontier AI research' — ensure this aligns with your actual experience to avoid misrepresentation in screening.",
      },
      {
        id: "rf-002",
        severity: "info",
        message: "JD mentions PyTorch and CUDA — these are not in your skills profile. Not blocking, but worth addressing in a cover letter addendum.",
      },
    ],
    steps: [
      {
        step_number: 0,
        action: "click",
        field_name: "Apply Now button",
        reasoning: "Green 'Apply Now' button is visible at center-right of viewport. No prior fields detected.",
        confidence: 0.97,
        x: 820,
        y: 312,
        timestamp: h(2),
        success: true,
      },
      {
        step_number: 1,
        action: "type",
        field_name: "first_name",
        value: "Kabiru",
        reasoning: "First Name input field is empty and in focus. Candidate profile provides first name.",
        confidence: 0.99,
        x: 512,
        y: 284,
        timestamp: h(2),
        success: true,
      },
      {
        step_number: 2,
        action: "type",
        field_name: "last_name",
        value: "Gacheru",
        reasoning: "Last Name field follows First Name, currently empty.",
        confidence: 0.98,
        x: 768,
        y: 284,
        timestamp: h(2),
        success: true,
      },
      {
        step_number: 3,
        action: "type",
        field_name: "email",
        value: "kabiru.gacheru@gmail.com",
        reasoning: "Email field detected below name fields, standard format required.",
        confidence: 0.99,
        x: 640,
        y: 340,
        timestamp: h(2),
        success: true,
      },
      {
        step_number: 4,
        action: "type",
        field_name: "phone",
        value: "+1-555-0147",
        reasoning: "Phone number field is visible and empty. Format appears to be US phone.",
        confidence: 0.94,
        x: 640,
        y: 396,
        timestamp: h(2),
        success: true,
      },
      {
        step_number: 5,
        action: "click",
        field_name: "Resume upload button",
        reasoning: "File upload button labeled 'Upload Resume' detected. Must attach CV before proceeding.",
        confidence: 0.96,
        x: 400,
        y: 480,
        timestamp: h(2),
        success: true,
      },
      {
        step_number: 6,
        action: "scroll",
        field_name: "page",
        reasoning: "Additional required fields suspected below viewport. Scrolling to reveal.",
        confidence: 0.88,
        x: 640,
        y: 400,
        timestamp: h(2),
        success: true,
      },
      {
        step_number: 7,
        action: "type",
        field_name: "linkedin_url",
        value: "https://linkedin.com/in/kabiru-gacheru",
        reasoning: "LinkedIn URL field detected in 'Links' section. Profile URL available from candidate data.",
        confidence: 0.97,
        x: 640,
        y: 540,
        timestamp: h(2),
        success: true,
      },
      {
        step_number: 8,
        action: "select",
        field_name: "years_of_experience",
        value: "5-8 years",
        reasoning: "Dropdown for years of experience. Candidate profile indicates 5 years — selecting matching range.",
        confidence: 0.91,
        x: 640,
        y: 620,
        timestamp: h(2),
        success: true,
      },
      {
        step_number: 9,
        action: "click",
        field_name: "Submit Application button",
        reasoning: "All required fields appear complete. Submit button is active and accessible.",
        confidence: 0.95,
        x: 640,
        y: 720,
        timestamp: h(2),
        success: true,
      },
      {
        step_number: 10,
        action: "done",
        field_name: "confirmation",
        reasoning: "Confirmation page detected: 'Application submitted successfully'. Task complete.",
        confidence: 0.99,
        x: 0,
        y: 0,
        timestamp: h(2),
        success: true,
      },
    ],
  },
  {
    id: "mock-002",
    company: "Stripe",
    title: "Platform Engineer",
    url: "jobs.lever.co/stripe/platform-engineer",
    ats_type: "lever",
    salary: "$195k – $260k",
    location: "Remote (US)",
    fit_score: 73,
    status: "running",
    created_at: h(1),
    submitted_at: null,
    keywords: ["Go", "Kubernetes", "gRPC", "Distributed Systems", "PostgreSQL", "AWS", "Python"],
    matched_keywords: ["Kubernetes", "Distributed Systems", "PostgreSQL", "AWS", "Python"],
    cover_letter: "",
    bullets: [],
    risk_flags: [],
    steps: [
      {
        step_number: 0,
        action: "click",
        field_name: "Apply button",
        reasoning: "Primary CTA button visible at top of job posting.",
        confidence: 0.98,
        x: 1100,
        y: 200,
        timestamp: h(1),
        success: true,
      },
    ],
  },
  {
    id: "mock-003",
    company: "Linear",
    title: "Senior Frontend Engineer",
    url: "jobs.ashbyhq.com/linear/senior-frontend",
    ats_type: "ashby",
    salary: "$180k – $240k",
    location: "Remote",
    fit_score: 91,
    status: "submitted",
    created_at: h(26),
    submitted_at: h(25),
    keywords: ["TypeScript", "React", "Next.js", "Performance", "GraphQL", "CSS", "Accessibility"],
    matched_keywords: ["TypeScript", "React", "Next.js", "GraphQL", "CSS"],
    cover_letter: "Dear Linear team,\n\nI've been a daily user of Linear for two years...",
    bullets: [
      "Rebuilt dashboard rendering pipeline in React 19 + TypeScript, cutting LCP from 2.8s to 0.6s",
      "Architected component library used across 4 product teams, covering 200+ accessible components",
      "Implemented real-time GraphQL subscriptions for collaborative editing with sub-50ms sync latency",
    ],
    risk_flags: [],
    steps: [],
  },
  {
    id: "mock-004",
    company: "Vercel",
    title: "Staff Engineer, Developer Experience",
    url: "boards.greenhouse.io/vercel/jobs/staff-devex",
    ats_type: "greenhouse",
    salary: "$220k – $310k",
    location: "Remote",
    fit_score: 82,
    status: "queued",
    created_at: h(0.1),
    submitted_at: null,
    keywords: ["Next.js", "TypeScript", "Node.js", "CDN", "Edge Computing", "Rust", "Python"],
    matched_keywords: ["Next.js", "TypeScript", "Node.js", "Python"],
    cover_letter: "",
    bullets: [],
    risk_flags: [],
    steps: [],
  },
  {
    id: "mock-005",
    company: "Scale AI",
    title: "Backend Engineer, Data Platform",
    url: "jobs.lever.co/scaleai/backend-data-platform",
    ats_type: "lever",
    salary: "$160k – $210k",
    location: "San Francisco, CA",
    fit_score: 38,
    status: "failed",
    created_at: h(72),
    submitted_at: null,
    keywords: ["Spark", "Flink", "Scala", "Kafka", "HDFS", "Databricks", "ML Pipelines"],
    matched_keywords: [],
    cover_letter: "",
    bullets: [],
    risk_flags: [],
    steps: [
      {
        step_number: 0,
        action: "error",
        field_name: "fit_threshold_not_met",
        error: "fit_threshold_not_met",
        fit_score: 38,
        threshold: 70,
        reasoning: "Fit score 38% is below configured threshold of 70%.",
        confidence: 1,
        x: 0,
        y: 0,
        timestamp: h(72),
        success: false,
      } as MockStep & { fit_score: number; threshold: number },
    ],
  },
];

export const MOCK_PROFILE = {
  user_id: "user-123",
  name: "Kabiru Gacheru",
  email: "kabiru.gacheru@gmail.com",
  phone: "+1-555-0147",
  location: "San Francisco, CA",
  linkedin_url: "https://linkedin.com/in/kabiru-gacheru",
  github_url: "https://github.com/kabiru24",
  skills: ["Python", "TypeScript", "FastAPI", "React", "Next.js", "PostgreSQL", "Redis", "Kubernetes", "AWS", "Terraform", "GraphQL", "Node.js"],
  experience: {
    "Senior Engineer @ TechCorp (2022–present)": [
      "Built and scaled distributed job queue processing 50k req/day",
      "Led Kubernetes migration for 12 microservices to AWS EKS",
      "Designed real-time analytics pipeline on AWS (SQS + Lambda + RDS)",
    ],
    "Software Engineer @ StartupXYZ (2020–2022)": [
      "Rebuilt React dashboard, improving LCP from 3.2s to 0.8s",
      "Built GraphQL API layer for mobile and web clients",
    ],
  },
  fit_threshold: 70,
};
