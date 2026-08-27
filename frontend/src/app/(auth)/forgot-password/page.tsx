"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AuthResetSchema } from "@/lib/validations";
import { z } from "zod";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { ErrorAlert } from "@/components/common/state-views";
import { CheckCircle2, ArrowLeft } from "lucide-react";

type ResetForm = z.infer<typeof AuthResetSchema>;

export default function ForgotPasswordPage() {
  const { resetPassword } = useAuth();
  const [submitted, setSubmitted] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetForm>({
    resolver: zodResolver(AuthResetSchema),
    defaultValues: {
      email: "",
    },
  });

  const onSubmit = async (data: ResetForm) => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      await resetPassword(data.email);
      setSubmitted(true);
    } catch (err: unknown) {
      const error = err as { message?: string };
      setErrorMsg(error.message || "Failed to send reset link. Please check the email address.");
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
          <p className="text-small text-secondary">Reset your account password</p>
        </div>

        {/* Card */}
        <Card>
          <CardHeader>
            <CardTitle>Password Reset</CardTitle>
            <CardDescription>
              {submitted
                ? "Check your inbox for reset instructions"
                : "Enter your registered email address"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {errorMsg && <ErrorAlert title="Error" message={errorMsg} />}

            {submitted ? (
              <div className="space-y-4 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-status-success-soft text-status-success">
                  <CheckCircle2 className="h-6 w-6" />
                </div>
                <p className="text-small text-secondary">
                  If an account exists for that email, we have sent a secure password reset link.
                </p>
                <Link href="/login">
                  <Button variant="outline" className="w-full">
                    Return to Sign In
                  </Button>
                </Link>
              </div>
            ) : (
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
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

                <Button type="submit" variant="primary" className="w-full" disabled={isLoading}>
                  {isLoading ? "Sending Link..." : "Send Reset Link"}
                </Button>

                <div className="pt-2 text-center">
                  <Link
                    href="/login"
                    className="inline-flex items-center gap-1 text-small text-secondary hover:text-primary"
                  >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    <span>Back to Sign In</span>
                  </Link>
                </div>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
