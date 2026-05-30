"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { CheckCircle2, Link2, MapPin, Mail, Phone, User, Briefcase, Plus, X } from "lucide-react";
import { api, type Profile } from "@/lib/api";
import { MOCK_PROFILE } from "@/lib/mock-data";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const DEFAULT_USER = "user-123";

const schema = z.object({
  name:          z.string().min(1, "Required"),
  email:         z.string().email("Invalid email"),
  phone:         z.string().optional(),
  location:      z.string().optional(),
  linkedin_url:  z.string().optional(),
  github_url:    z.string().optional(),
  skills_raw:    z.string(),
  fit_threshold: z.coerce.number().min(0).max(100),
});

type FormValues = z.infer<typeof schema>;

const inputCls = "h-8 w-full rounded-md border border-gray-300 bg-white px-3 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-shadow";

function Label({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <label className="block text-xs font-medium text-gray-600 mb-1.5">
      {children}{required && <span className="text-red-500 ml-0.5">*</span>}
    </label>
  );
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p className="text-xs text-red-500 mt-1">{message}</p>;
}

function Section({ title, icon: Icon, children }: { title: string; icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-gray-200 p-5">
      <div className="flex items-center gap-2 mb-4">
        <Icon className="h-4 w-4 text-gray-400" />
        <h2 className="text-sm font-semibold text-gray-800">{title}</h2>
      </div>
      {children}
    </div>
  );
}

export default function ProfilePage() {
  const qc = useQueryClient();
  const [skillInput, setSkillInput] = useState("");
  const [skills, setSkills] = useState<string[]>([]);

  const { data: profile, isLoading } = useQuery({
    queryKey: ["profile", DEFAULT_USER],
    queryFn: () => api.getProfile(DEFAULT_USER).catch(() => null),
  });

  const save = useMutation({
    mutationFn: (values: FormValues) => {
      const data: Profile = {
        user_id: DEFAULT_USER,
        name: values.name,
        email: values.email,
        phone: values.phone || null,
        location: values.location || null,
        linkedin_url: values.linkedin_url || null,
        github_url: values.github_url || null,
        skills,
        experience: {},
        fit_threshold: values.fit_threshold,
      };
      return api.upsertProfile(data);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["profile"] }),
  });

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isDirty },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      fit_threshold: MOCK_PROFILE.fit_threshold,
      skills_raw: "",
      name: MOCK_PROFILE.name,
      email: MOCK_PROFILE.email,
      phone: MOCK_PROFILE.phone ?? "",
      location: MOCK_PROFILE.location ?? "",
      linkedin_url: MOCK_PROFILE.linkedin_url ?? "",
      github_url: MOCK_PROFILE.github_url ?? "",
    },
  });

  useEffect(() => {
    const src = profile ?? MOCK_PROFILE;
    reset({
      name: src.name,
      email: src.email,
      phone: src.phone ?? "",
      location: src.location ?? "",
      linkedin_url: src.linkedin_url ?? "",
      github_url: src.github_url ?? "",
      skills_raw: "",
      fit_threshold: src.fit_threshold,
    });
    setSkills(src.skills ?? []);
  }, [profile, reset]);

  const fitThreshold = watch("fit_threshold") ?? 70;

  function addSkill() {
    const trimmed = skillInput.trim();
    if (trimmed && !skills.includes(trimmed)) {
      setSkills((s) => [...s, trimmed]);
    }
    setSkillInput("");
  }

  function removeSkill(skill: string) {
    setSkills((s) => s.filter((x) => x !== skill));
  }

  function onSkillKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addSkill();
    }
  }

  const thresholdColor =
    fitThreshold >= 80 ? "text-emerald-600" :
    fitThreshold >= 60 ? "text-amber-600" : "text-red-500";
  const trackFill =
    fitThreshold >= 80 ? "bg-emerald-500" :
    fitThreshold >= 60 ? "bg-amber-500" : "bg-red-500";

  if (isLoading) {
    return (
      <div className="px-6 py-6 space-y-4 max-w-2xl">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="rounded-lg border border-gray-200 p-5 space-y-3">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
        <div>
          <h1 className="text-base font-semibold text-gray-900">Profile</h1>
          <p className="text-xs text-gray-400 mt-0.5">Your candidate profile used for fit scoring and tailoring</p>
        </div>
        {save.isSuccess && (
          <span className="flex items-center gap-1.5 text-xs text-emerald-600 font-medium">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Saved
          </span>
        )}
      </div>

      <form
        onSubmit={handleSubmit((v) => save.mutate(v))}
        className="flex-1 overflow-y-auto px-6 py-5"
      >
        <div className="max-w-2xl space-y-4">
          {/* Identity */}
          <Section title="Identity" icon={User}>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label required>Full name</Label>
                <input {...register("name")} placeholder="Kabiru Gacheru" className={inputCls} />
                <FieldError message={errors.name?.message} />
              </div>
              <div>
                <Label required>Email</Label>
                <div className="relative">
                  <Mail className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
                  <input {...register("email")} type="email" placeholder="you@example.com" className={cn(inputCls, "pl-8")} />
                </div>
                <FieldError message={errors.email?.message} />
              </div>
              <div>
                <Label>Phone</Label>
                <div className="relative">
                  <Phone className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
                  <input {...register("phone")} placeholder="+1-555-0001" className={cn(inputCls, "pl-8")} />
                </div>
              </div>
              <div>
                <Label>Location</Label>
                <div className="relative">
                  <MapPin className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
                  <input {...register("location")} placeholder="San Francisco, CA" className={cn(inputCls, "pl-8")} />
                </div>
              </div>
            </div>
          </Section>

          {/* Links */}
          <Section title="Links" icon={Briefcase}>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>LinkedIn</Label>
                <div className="relative">
                  <Link2 className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
                  <input {...register("linkedin_url")} placeholder="linkedin.com/in/…" className={cn(inputCls, "pl-8")} />
                </div>
              </div>
              <div>
                <Label>GitHub</Label>
                <div className="relative">
                  <Link2 className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
                  <input {...register("github_url")} placeholder="github.com/…" className={cn(inputCls, "pl-8")} />
                </div>
              </div>
            </div>
          </Section>

          {/* Skills */}
          <Section title="Skills" icon={CheckCircle2}>
            <div className="space-y-3">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={skillInput}
                  onChange={(e) => setSkillInput(e.target.value)}
                  onKeyDown={onSkillKeyDown}
                  placeholder="Add a skill and press Enter…"
                  className={cn(inputCls, "flex-1")}
                />
                <Button type="button" variant="outline" size="sm" onClick={addSkill}>
                  <Plus className="h-3.5 w-3.5" />
                </Button>
              </div>
              {skills.length > 0 ? (
                <div className="flex flex-wrap gap-1.5 p-3 rounded-md bg-gray-50 border border-gray-200 min-h-[52px]">
                  {skills.map((s) => (
                    <span
                      key={s}
                      className="inline-flex items-center gap-1 bg-white border border-gray-200 px-2 py-0.5 rounded text-xs font-medium text-gray-700 shadow-sm"
                    >
                      {s}
                      <button
                        type="button"
                        onClick={() => removeSkill(s)}
                        className="text-gray-400 hover:text-gray-700 ml-0.5"
                      >
                        <X className="h-2.5 w-2.5" />
                      </button>
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-gray-400 italic px-1">No skills added yet</p>
              )}
            </div>
          </Section>

          {/* Fit threshold */}
          <Section title="Fit Threshold" icon={CheckCircle2}>
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <input
                  {...register("fit_threshold", { valueAsNumber: true })}
                  type="range"
                  min={0}
                  max={100}
                  step={5}
                  className="flex-1 accent-indigo-600"
                />
                <span className={cn("text-xl font-semibold tabular-nums w-14 text-right", thresholdColor)}>
                  {fitThreshold}%
                </span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-gray-100 overflow-hidden">
                <div
                  className={cn("h-full rounded-full transition-all duration-200", trackFill)}
                  style={{ width: `${fitThreshold}%` }}
                />
              </div>
              <p className="text-xs text-gray-400 leading-relaxed">
                The agent only applies when your keyword match score is at or above this threshold.
                Setting it below <strong>60%</strong> increases volume but reduces interview conversion.
                Default is <strong>70%</strong>.
              </p>
            </div>
          </Section>

          {/* Submit */}
          <div className="flex items-center gap-3 pt-1 pb-6">
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? "Saving…" : "Save profile"}
            </Button>
            {save.isError && (
              <p className="text-xs text-red-500">{(save.error as Error).message}</p>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}
