import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Clock,
  Eye,
  EyeOff,
  Lock,
  Mail,
  MapPin,
  ShieldCheck,
  User,
} from "lucide-react";
import { apiClient } from "@/services/api";

const registerSchema = z.object({
  name: z.string().min(2, { message: "Name must be at least 2 characters" }),
  email: z.string().email({ message: "Please enter a valid official email address" }),
  password: z.string().min(8, { message: "Password must be at least 8 characters" }),
  district: z.string().min(2, { message: "District is required" }),
  state: z.string().min(2, { message: "State is required" }),
});

type RegisterFormValues = z.infer<typeof registerSchema>;

export const RegisterPage: React.FC = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data: RegisterFormValues) => {
    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      await apiClient.post("/api/v1/auth/register", data);
      setIsSuccess(true);
    } catch (err: any) {
      if (err.response?.status === 409) {
        setErrorMessage("An account with this email address already exists.");
      } else {
        setErrorMessage(
          err.response?.data?.detail || "Registration failed. Please check your details."
        );
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isSuccess) {
    return (
      <div className="min-h-[75vh] flex flex-col justify-center items-center px-4">
        <div className="w-full max-w-md bg-white border border-slate-200 rounded-xl shadow-sm p-8 text-center">
          <div className="inline-flex bg-emerald-50 text-emerald-600 p-4 rounded-full mb-4">
            <CheckCircle2 className="w-10 h-10" />
          </div>
          <h2 className="text-xl font-bold text-slate-900">Application Submitted</h2>
          <div className="mt-3 p-4 rounded-lg bg-amber-50 border border-amber-200 text-left text-xs text-amber-900 leading-relaxed flex items-start gap-2.5">
            <Clock className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold block text-amber-950 mb-0.5">
                Pending Administrator Approval
              </span>
              Your account has been registered with Viewer credentials. In accordance with
              departmental security protocols, an administrator will verify and activate your
              account before access is granted.
            </div>
          </div>
          <Link
            to="/login"
            className="mt-6 w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg shadow-sm transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Return to Login</span>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[75vh] flex flex-col justify-center items-center px-4 py-8">
      <div className="w-full max-w-md bg-white border border-slate-200 rounded-xl shadow-sm p-8">
        <div className="text-center mb-6">
          <div className="inline-flex bg-blue-50 p-3 rounded-xl mb-3 text-blue-600 ring-4 ring-blue-50/50">
            <ShieldCheck className="w-8 h-8" />
          </div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            Register for Viewer Access
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Departmental & Enforcement Monitoring Portal
          </p>
        </div>

        {errorMessage && (
          <div className="mb-5 p-3 rounded-lg bg-red-50 border border-red-200 text-red-800 flex items-start gap-2.5 text-xs">
            <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold block">Registration Error</span>
              {errorMessage}
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div>
            <label
              htmlFor="name-input"
              className="block text-xs font-semibold text-slate-700 mb-1"
            >
              Full Name
            </label>
            <div className="relative">
              <User className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                id="name-input"
                type="text"
                autoComplete="name"
                {...register("name")}
                className="w-full pl-9 pr-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Ramesh Kumar"
              />
            </div>
            {errors.name && (
              <p className="text-[11px] text-red-600 mt-1 font-medium">{errors.name.message}</p>
            )}
          </div>

          <div>
            <label
              htmlFor="reg-email-input"
              className="block text-xs font-semibold text-slate-700 mb-1"
            >
              Official Email Address
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                id="reg-email-input"
                type="email"
                autoComplete="username"
                {...register("email")}
                className="w-full pl-9 pr-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="name@dept.gov.in"
              />
            </div>
            {errors.email && (
              <p className="text-[11px] text-red-600 mt-1 font-medium">
                {errors.email.message}
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label
                htmlFor="district-input"
                className="block text-xs font-semibold text-slate-700 mb-1"
              >
                District
              </label>
              <div className="relative">
                <MapPin className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  id="district-input"
                  type="text"
                  {...register("district")}
                  className="w-full pl-9 pr-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g. Pune"
                />
              </div>
              {errors.district && (
                <p className="text-[11px] text-red-600 mt-1 font-medium">
                  {errors.district.message}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="state-input"
                className="block text-xs font-semibold text-slate-700 mb-1"
              >
                State
              </label>
              <input
                id="state-input"
                type="text"
                {...register("state")}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Maharashtra"
              />
              {errors.state && (
                <p className="text-[11px] text-red-600 mt-1 font-medium">
                  {errors.state.message}
                </p>
              )}
            </div>
          </div>

          <div>
            <label
              htmlFor="reg-password-input"
              className="block text-xs font-semibold text-slate-700 mb-1"
            >
              Password (min 8 characters)
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                id="reg-password-input"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                {...register("password")}
                className="w-full pl-9 pr-10 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                aria-pressed={showPassword}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
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
              <span>Submitting Application...</span>
            ) : (
              <>
                <span>Submit Registration Request</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        <div className="mt-6 pt-4 border-t border-slate-100 text-center text-xs text-slate-500">
          Already have an account?{" "}
          <Link to="/login" className="text-blue-600 font-semibold hover:underline">
            Sign In
          </Link>
        </div>
      </div>
    </div>
  );
};
