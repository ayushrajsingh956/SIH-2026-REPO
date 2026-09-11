import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Users,
  UserPlus,
  Shield,
  Search,
  CheckCircle2,
  Clock,
  Filter,
  RefreshCw,
} from "lucide-react";
import { apiClient } from "@/services/api";
import { Badge, BadgeVariant } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";

interface UserItem {
  id: string;
  name: string;
  email: string;
  role: "admin" | "inspector" | "viewer";
  district: string | null;
  state: string | null;
  is_active: boolean;
  created_at: string;
}

export const UsersManagementPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [activeFilter, setActiveFilter] = useState<string>("");

  // Create User Modal State
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    name: "",
    email: "",
    password: "",
    role: "inspector",
    district: "",
    state: "Delhi",
  });
  const [createError, setCreateError] = useState<string | null>(null);

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["admin-users", page, roleFilter, activeFilter, searchQuery],
    queryFn: async () => {
      const params = new URLSearchParams({
        page: page.toString(),
        limit: "20",
      });
      if (roleFilter) params.append("role", roleFilter);
      if (activeFilter !== "") params.append("is_active", activeFilter);
      if (searchQuery.trim()) params.append("q", searchQuery.trim());

      const res = await apiClient.get(`/api/v1/admin/users?${params.toString()}`);
      return res.data;
    },
  });

  const users: UserItem[] = data?.items || [];
  const total = data?.total || 0;

  // Mutation: Update Role
  const updateRoleMutation = useMutation({
    mutationFn: async ({ userId, role }: { userId: string; role: string }) => {
      await apiClient.patch(`/api/v1/admin/users/${userId}`, { role });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });

  // Mutation: Toggle Active Status
  const toggleActiveMutation = useMutation({
    mutationFn: async ({ userId, isActive }: { userId: string; isActive: boolean }) => {
      await apiClient.patch(`/api/v1/admin/users/${userId}`, { is_active: isActive });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });

  // Mutation: Create User
  const createUserMutation = useMutation({
    mutationFn: async (payload: typeof createForm) => {
      const res = await apiClient.post("/api/v1/admin/users", payload);
      return res.data;
    },
    onSuccess: () => {
      setIsCreateOpen(false);
      setCreateForm({
        name: "",
        email: "",
        password: "",
        role: "inspector",
        district: "",
        state: "Delhi",
      });
      setCreateError(null);
      void queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (err: any) => {
      setCreateError(
        err.response?.data?.detail || "Failed to provision officer account. Please verify input details."
      );
    },
  });

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!createForm.name || !createForm.email || !createForm.password) {
      setCreateError("Name, email, and password are required.");
      return;
    }
    createUserMutation.mutate(createForm);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Users className="w-5 h-5 text-blue-600" />
            Enforcement Officer &amp; User Administration
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Manage officer roles, approve pending accounts, and provision field inspector credentials.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void refetch()}
            disabled={isFetching}
            className="gap-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={() => {
              setCreateError(null);
              setIsCreateOpen(true);
            }}
            className="gap-1.5"
          >
            <UserPlus className="w-4 h-4" />
            Provision New Officer
          </Button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-3 flex-1 min-w-[280px]">
          <div className="relative flex-1 max-w-sm">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search by name or email..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 rounded-lg border border-slate-200 text-xs focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 outline-none"
            />
          </div>

          <div className="flex items-center gap-1.5 text-slate-600">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-xs text-slate-700 outline-none focus:border-blue-500"
            >
              <option value="">All Roles</option>
              <option value="admin">Admin</option>
              <option value="inspector">Inspector</option>
              <option value="viewer">Viewer</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5 text-slate-600">
            <select
              value={activeFilter}
              onChange={(e) => setActiveFilter(e.target.value)}
              className="px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-xs text-slate-700 outline-none focus:border-blue-500"
            >
              <option value="">All Statuses</option>
              <option value="true">Active Only</option>
              <option value="false">Pending / Deactivated</option>
            </select>
          </div>
        </div>

        <div className="text-xs font-semibold text-slate-500">
          Showing <span className="text-slate-900">{users.length}</span> of{" "}
          <span className="text-slate-900">{total}</span> users
        </div>
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-slate-400 text-xs animate-pulse">
            Loading officer records...
          </div>
        ) : users.length === 0 ? (
          <div className="p-12 text-center">
            <Shield className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <div className="text-sm font-semibold text-slate-700">No users match criteria</div>
            <p className="text-xs text-slate-400 mt-1">Adjust your search or filter settings.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200 uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3 px-4">Officer Name &amp; Email</th>
                  <th className="py-3 px-4">Role Assignment</th>
                  <th className="py-3 px-4">Jurisdiction / District</th>
                  <th className="py-3 px-4">Account Status</th>
                  <th className="py-3 px-4">Registration Date</th>
                  <th className="py-3 px-4 text-right">Administrative Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-bold text-slate-900">{u.name}</div>
                      <div className="text-slate-500 font-mono text-[11px]">{u.email}</div>
                    </td>

                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <Badge variant={u.role as BadgeVariant} size="sm">
                          {u.role.toUpperCase()}
                        </Badge>
                        <select
                          value={u.role}
                          onChange={(e) =>
                            updateRoleMutation.mutate({ userId: u.id, role: e.target.value })
                          }
                          disabled={updateRoleMutation.isPending}
                          className="text-[11px] border border-slate-200 rounded px-1.5 py-0.5 bg-white text-slate-700 focus:outline-none focus:border-blue-500"
                        >
                          <option value="admin">Admin</option>
                          <option value="inspector">Inspector</option>
                          <option value="viewer">Viewer</option>
                        </select>
                      </div>
                    </td>

                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-800">
                        {u.district || "National"}
                      </div>
                      <div className="text-[10px] text-slate-400">{u.state || "India"}</div>
                    </td>

                    <td className="py-3 px-4">
                      {u.is_active ? (
                        <span className="inline-flex items-center gap-1 text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full text-[10px] font-bold border border-emerald-200">
                          <CheckCircle2 className="w-3 h-3" />
                          ACTIVE
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full text-[10px] font-bold border border-amber-200">
                          <Clock className="w-3 h-3" />
                          PENDING APPROVAL
                        </span>
                      )}
                    </td>

                    <td className="py-3 px-4 text-slate-400 text-[11px]">
                      {new Date(u.created_at).toLocaleDateString("en-IN", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </td>

                    <td className="py-3 px-4 text-right">
                      {u.is_active ? (
                        <button
                          type="button"
                          onClick={() =>
                            toggleActiveMutation.mutate({ userId: u.id, isActive: false })
                          }
                          disabled={toggleActiveMutation.isPending}
                          className="text-xs text-rose-600 hover:text-rose-700 font-semibold px-2 py-1 rounded hover:bg-rose-50 border border-transparent hover:border-rose-200 transition-colors"
                        >
                          Deactivate
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() =>
                            toggleActiveMutation.mutate({ userId: u.id, isActive: true })
                          }
                          disabled={toggleActiveMutation.isPending}
                          className="text-xs text-emerald-700 hover:text-emerald-800 font-semibold px-2 py-1 rounded hover:bg-emerald-50 border border-emerald-300 bg-emerald-50/50 transition-colors"
                        >
                          Approve / Activate
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Controls */}
        {total > 20 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200 text-xs text-slate-500 bg-slate-50">
            <div>
              Page <span className="font-bold text-slate-800">{page}</span> of{" "}
              <span className="font-bold text-slate-800">{Math.ceil(total / 20)}</span>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= Math.ceil(total / 20)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Provision Officer Modal Dialog */}
      <Dialog
        open={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Provision Enforcement Officer / User"
        description="Creates an authorized account for statutory compliance enforcement."
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4 pt-2 text-xs">
          {createError && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs">
              {createError}
            </div>
          )}

          <div>
            <label className="block font-semibold text-slate-700 mb-1">Officer Full Name *</label>
            <input
              type="text"
              required
              value={createForm.name}
              onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
              placeholder="e.g., Insp. Suresh Verma"
              className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 outline-none text-xs"
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">Official Email Address *</label>
            <input
              type="email"
              required
              value={createForm.email}
              onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
              placeholder="e.g., suresh.verma@legalmetro.gov.in"
              className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 outline-none text-xs"
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">Initial Password *</label>
            <input
              type="password"
              required
              value={createForm.password}
              onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
              placeholder="Minimum 8 characters"
              className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 outline-none text-xs"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Role *</label>
              <select
                value={createForm.role}
                onChange={(e) => setCreateForm({ ...createForm, role: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-white text-xs outline-none focus:border-blue-600"
              >
                <option value="inspector">Inspector (Field)</option>
                <option value="admin">Administrator</option>
                <option value="viewer">Viewer (Read-Only)</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">District / Cell</label>
              <input
                type="text"
                value={createForm.district}
                onChange={(e) => setCreateForm({ ...createForm, district: e.target.value })}
                placeholder="e.g. South Delhi"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 outline-none text-xs"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t border-slate-100">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsCreateOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={createUserMutation.isPending}
            >
              {createUserMutation.isPending ? "Creating..." : "Create Account"}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
};
