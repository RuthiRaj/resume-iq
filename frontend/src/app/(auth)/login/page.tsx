"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AuthLoginSchema } from "@/lib/validations";
import { z } from "zod";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { ErrorAlert } from "@/components/common/state-views";

type LoginForm = z.infer<typeof AuthLoginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const { signIn } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(AuthLoginSchema),
    defaultValues: {
      email: "",
      password: "",
      rememberMe: true,
    },
  });

  const onSubmit = async (data: LoginForm) => {
    setIsLoading(true);
    setAuthError(null);
    try {
      await signIn(data.email, data.password);
      router.push("/dashboard");
    } catch (err: unknown) {
      const error = err as { code?: string; message?: string };
      if (error.code === "auth/invalid-credential" || error.code === "auth/user-not-found" || error.code === "auth/wrong-password") {
        setAuthError("Invalid email or password. Please check your credentials or create a new account.");
      } else {
        setAuthError(error.message || "Failed to sign in. Please try again.");
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
          <p className="text-small text-secondary">Sign in to access your unified career workspace</p>
        </div>

        {/* Login Card */}
        <Card>
          <CardHeader>
            <CardTitle>Sign in to your account</CardTitle>
            <CardDescription>Enter your credentials to continue</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {authError && (
              <ErrorAlert
                title="Authentication Error"
                message={authError}
              />
            )}

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

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-small font-medium text-primary">Password</label>
                  <Link
                    href="/forgot-password"
                    className="text-small text-accent hover:underline"
                  >
                    Forgot password?
                  </Link>
                </div>
                <Input
                  type="password"
                  placeholder="••••••••"
                  {...register("password")}
                  className={errors.password ? "border-status-error" : ""}
                />
                {errors.password && (
                  <p className="text-caption text-status-error">{errors.password.message}</p>
                )}
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="remember"
                  {...register("rememberMe")}
                  className="rounded border-border text-accent focus:ring-accent"
                />
                <label htmlFor="remember" className="text-small text-secondary cursor-pointer">
                  Remember this device for 30 days
                </label>
              </div>

              <Button type="submit" variant="primary" className="w-full" disabled={isLoading}>
                {isLoading ? "Signing in..." : "Sign In to Workspace"}
              </Button>
            </form>

            <div className="pt-2 text-center text-small text-secondary">
              Don&apos;t have an account?{" "}
              <Link href="/register" className="font-medium text-accent hover:underline">
                Create an account
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
