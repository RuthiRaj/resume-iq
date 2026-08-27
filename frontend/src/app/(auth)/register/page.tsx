"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AuthRegisterSchema } from "@/lib/validations";
import { z } from "zod";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { ErrorAlert } from "@/components/common/state-views";
import { ShieldCheck } from "lucide-react";

type RegisterForm = z.infer<typeof AuthRegisterSchema>;

export default function RegisterPage() {
  const router = useRouter();
  const { signUp } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterForm>({
    resolver: zodResolver(AuthRegisterSchema),
    defaultValues: {
      fullName: "",
      email: "",
      password: "",
      confirmPassword: "",
    },
  });

  const onSubmit = async (data: RegisterForm) => {
    setIsLoading(true);
    setAuthError(null);
    try {
      await signUp(data.fullName, data.email, data.password);
      router.push("/dashboard");
    } catch (err: unknown) {
      const error = err as { code?: string; message?: string };
      if (error.code === "auth/email-already-in-use") {
        setAuthError("An account with this email address already exists. Please sign in instead.");
      } else if (error.code === "auth/weak-password") {
        setAuthError("Password is too weak. Please use at least 8 characters with numbers or symbols.");
      } else {
        setAuthError(error.message || "Failed to create account. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-page flex flex-col justify-center items-center p-4 sm:p-6">
      <div className="w-full max-w-md space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <Link href="/" className="inline-flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-[6px] bg-accent text-white font-semibold text-body">
              R
            </div>
            <span className="text-h1 font-semibold tracking-tight text-primary">ResumeIQ</span>
          </Link>
          <p className="text-small text-secondary">Start your personal AI career intelligence workspace</p>
        </div>

        {/* Register Card */}
        <Card>
          <CardHeader>
            <CardTitle>Create your account</CardTitle>
            <CardDescription>Free career workspace with ATS intelligence</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {authError && (
              <ErrorAlert
                title="Registration Error"
                message={authError}
              />
            )}

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-small font-medium text-primary">Full Name</label>
                <Input
                  placeholder="e.g. Alex Morgan"
                  {...register("fullName")}
                  className={errors.fullName ? "border-status-error" : ""}
                />
                {errors.fullName && (
                  <p className="text-caption text-status-error">{errors.fullName.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="text-small font-medium text-primary">Email address</label>
                <Input
                  type="email"
                  placeholder="name@example.com"
                  {...register("email")}
                  className={errors.email ? "border-status-error" : ""}
                />
                {errors.email && (
                  <p className="text-caption text-status-error">{errors.email.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="text-small font-medium text-primary">Password</label>
                <Input
                  type="password"
                  placeholder="At least 8 characters"
                  {...register("password")}
                  className={errors.password ? "border-status-error" : ""}
                />
                {errors.password && (
                  <p className="text-caption text-status-error">{errors.password.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="text-small font-medium text-primary">Confirm Password</label>
                <Input
                  type="password"
                  placeholder="Repeat your password"
                  {...register("confirmPassword")}
                  className={errors.confirmPassword ? "border-status-error" : ""}
                />
                {errors.confirmPassword && (
                  <p className="text-caption text-status-error">{errors.confirmPassword.message}</p>
                )}
              </div>

              <div className="flex items-center gap-2 text-caption text-secondary">
                <ShieldCheck className="h-4 w-4 text-status-success shrink-0" />
                <span>Zero telemetry or unsolicited data sharing</span>
              </div>

              <Button type="submit" variant="primary" className="w-full" disabled={isLoading}>
                {isLoading ? "Creating account..." : "Create Workspace Account"}
              </Button>
            </form>

            <div className="pt-2 text-center text-small text-secondary">
              Already have an account?{" "}
              <Link href="/login" className="font-medium text-accent hover:underline">
                Sign in
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
