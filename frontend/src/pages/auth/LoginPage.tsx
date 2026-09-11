import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
  AlertCircle,
  ArrowRight,
  Clock,
  Eye,
  EyeOff,
  Lock,
  Mail,
  ShieldCheck,
} from "lucide-react";
import { apiClient } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";

const loginSchema = z.object({
  email: z.string().email({ message: "Please enter a valid official email address" }),
  password: z.string().min(1, { message: "Password is required" }),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export const LoginPage: React.FC = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [authError, setAuthError] = useState<{
    type: "invalid_credentials" | "pending_approval" | "general";
    message: string;
  } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as any)?.from?.pathname || "/dashboard";

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "admin.doca@nic.in",
      password: "AdminPassword123!",
    },
  });

  const onSubmit = async (data: LoginFormValues) => {
    setAuthError(null);
    setIsSubmitting(true);

    try {
      const response = await apiClient.post("/api/v1/auth/login", data);
      const { access_token, refresh_token, user } = response.data;

      login(
        {
          accessToken: access_token,
          refreshToken: refresh_token,
        },
        user
      );

      navigate(from, { replace: true });
    } catch (err: any) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail;

      if (status === 403) {
        setAuthError({
          type: "pending_approval",
          message:
            detail ||
            "Your account registration is currently pending administrator verification. Please contact your departmental nodal officer.",
        });
      } else if (status === 401) {
        setAuthError({
          type: "invalid_credentials",
          message: "Incorrect email address or password. Please verify your credentials.",
        });
      } else {
        setAuthError({
          type: "general",
          message: detail || "Unable to connect to the authentication server. Please try again.",
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-[75vh] flex flex-col justify-center items-center px-4">
      <div className="w-full max-w-md bg-white border border-slate-200 rounded-xl shadow-sm p-8">
        {/* Header Branding */}
        <div className="text-center mb-6">
          <div className="inline-flex bg-blue-50 p-3 rounded-xl mb-3 text-blue-600 ring-4 ring-blue-50/50">
            <ShieldCheck className="w-8 h-8" />
          </div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            Enforcement Officer Login
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Department of Consumer Affairs &bull; Legal Metrology Division
          </p>
        </div>

        {/* Error Banners */}
        {authError?.type === "pending_approval" && (
          <div className="mb-5 p-4 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 flex items-start gap-3 text-xs leading-relaxed">
            <Clock className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold block text-amber-950">Registration Pending Approval</span>
              {authError.message}
            </div>
          </div>
        )}

        {authError && authError.type !== "pending_approval" && (
          <div className="mb-5 p-3.5 rounded-lg bg-red-50 border border-red-200 text-red-800 flex items-start gap-2.5 text-xs">
            <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold block">Authentication Failed</span>
              {authError.message}
            </div>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div>
            <label
              htmlFor="email-input"
              className="block text-xs font-semibold text-slate-700 mb-1"
            >
              Official Email Address
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                id="email-input"
                type="email"
                autoComplete="username"
                {...register("email")}
                aria-invalid={errors.email ? "true" : "false"}
                className={`w-full pl-9 pr-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 transition-colors ${
                  errors.email
                    ? "border-red-400 focus:ring-red-200"
                    : "border-slate-300 focus:ring-blue-500"
                }`}
                placeholder="officer@nic.in"
              />
            </div>
            {errors.email && (
              <p className="text-[11px] text-red-600 mt-1 font-medium">
                {errors.email.message}
              </p>
            )}
          </div>

          <div>
            <div className="flex justify-between items-center mb-1">
              <label
                htmlFor="password-input"
                className="text-xs font-semibold text-slate-700"
              >
                Password
              </label>
            </div>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                id="password-input"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                {...register("password")}
                aria-invalid={errors.password ? "true" : "false"}
                className={`w-full pl-9 pr-10 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 transition-colors ${
                  errors.password
                    ? "border-red-400 focus:ring-red-200"
                    : "border-slate-300 focus:ring-blue-500"
                }`}
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                aria-pressed={showPassword}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600 transition-colors"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {errors.password && (
              <p className="text-[11px] text-red-600 mt-1 font-medium">
                {errors.password.message}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full mt-2 flex items-center justify-center gap-2 py-2.5 px-4 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-70 text-white text-sm font-semibold rounded-lg shadow-sm transition-all"
          >
            {isSubmitting ? (
              <span>Verifying Credentials...</span>
            ) : (
              <>
                <span>Sign In to Enforcement Portal</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        <div className="mt-6 pt-4 border-t border-slate-100 flex flex-col items-center gap-3 text-xs text-slate-500">
          <div>
            Don't have an account?{" "}
            <Link
              to="/register"
              className="text-blue-600 font-semibold hover:underline"
            >
              Register as Viewer / Analyst
            </Link>
          </div>
          <p className="text-[11px] text-slate-400 text-center">
            Authorized personnel only. All access is logged for audit compliance under Legal Metrology Act, 2009.
          </p>
        </div>
      </div>
    </div>
  );
};
