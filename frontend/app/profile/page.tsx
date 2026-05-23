"use client";

import { useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { api, type Profile } from "@/lib/api";

const DEFAULT_USER = "user-123";

const schema = z.object({
  name: z.string().min(1, "Required"),
  email: z.string().email("Invalid email"),
  phone: z.string().optional(),
  location: z.string().optional(),
  linkedin_url: z.string().optional(),
  github_url: z.string().optional(),
  skills_raw: z.string(), // comma-separated
  fit_threshold: z.coerce.number().min(0).max(100),
});

type FormValues = z.infer<typeof schema>;

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      {children}
      {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
    </div>
  );
}

const inputCls = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500";

export default function ProfilePage() {
  const qc = useQueryClient();

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
        skills: values.skills_raw.split(",").map((s) => s.trim()).filter(Boolean),
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
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { fit_threshold: 70, skills_raw: "" },
  });

  useEffect(() => {
    if (profile) {
      reset({
        name: profile.name,
        email: profile.email,
        phone: profile.phone ?? "",
        location: profile.location ?? "",
        linkedin_url: profile.linkedin_url ?? "",
        github_url: profile.github_url ?? "",
        skills_raw: profile.skills.join(", "),
        fit_threshold: profile.fit_threshold,
      });
    }
  }, [profile, reset]);

  if (isLoading) return <div className="text-sm text-gray-500">Loading…</div>;

  return (
    <div className="max-w-xl">
      <h1 className="text-2xl font-bold mb-6">Profile</h1>

      <form onSubmit={handleSubmit((v) => save.mutate(v))} className="space-y-4">
        <Field label="Full name" error={errors.name?.message}>
          <input {...register("name")} className={inputCls} />
        </Field>

        <Field label="Email" error={errors.email?.message}>
          <input {...register("email")} type="email" className={inputCls} />
        </Field>

        <Field label="Phone">
          <input {...register("phone")} className={inputCls} placeholder="+1-555-0001" />
        </Field>

        <Field label="Location">
          <input {...register("location")} className={inputCls} placeholder="City, Country" />
        </Field>

        <Field label="LinkedIn URL">
          <input {...register("linkedin_url")} className={inputCls} placeholder="https://linkedin.com/in/…" />
        </Field>

        <Field label="GitHub URL">
          <input {...register("github_url")} className={inputCls} placeholder="https://github.com/…" />
        </Field>

        <Field label="Skills (comma-separated)">
          <input {...register("skills_raw")} className={inputCls} placeholder="python, fastapi, react, postgres" />
        </Field>

        <Field label={`Fit threshold: ${errors.fit_threshold ? "" : ""}`} error={errors.fit_threshold?.message}>
          <div className="flex items-center gap-3">
            <input
              {...register("fit_threshold")}
              type="range"
              min={0}
              max={100}
              className="flex-1"
            />
            <span className="text-sm w-10 text-right text-gray-700">
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Only apply to jobs above this keyword match score (default 70%).
          </p>
        </Field>

        <div className="pt-2">
          <button
            type="submit"
            disabled={isSubmitting || save.isPending}
            className="bg-indigo-600 text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
          >
            {save.isPending ? "Saving…" : "Save profile"}
          </button>
          {save.isSuccess && (
            <span className="ml-3 text-sm text-green-600">Saved!</span>
          )}
        </div>
      </form>
    </div>
  );
}
