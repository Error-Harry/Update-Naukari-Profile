import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
  Activity,
  CheckCircle2,
  CircleDollarSign,
  Loader2,
  Search,
  ShieldAlert,
  Users,
  XCircle,
} from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  api,
  ApiError,
  type AdminRunLog,
  type AdminStats,
  type AdminUser,
} from "@/lib/api";
import { formatDateTime } from "@/lib/utils";

export function AdminPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <ShieldAlert className="h-6 w-6 text-primary" /> Admin
        </h1>
        <p className="text-muted-foreground">
          Manage users, subscriptions and monitor run activity.
        </p>
      </div>

      <StatsGrid />
      <UsersTable />
      <RunsTable />
    </div>
  );
}

// ----------------- Stats -----------------

function StatsGrid() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-stats"],
    queryFn: () => api<AdminStats>("/api/admin/stats"),
    refetchInterval: 30_000,
  });

  const tiles = [
    {
      label: "Total users",
      value: data?.total_users ?? 0,
      icon: <Users className="h-4 w-4" />,
    },
    {
      label: "Paid users",
      value: data?.paid_users ?? 0,
      icon: <CircleDollarSign className="h-4 w-4" />,
    },
    {
      label: "Enabled profiles",
      value: `${data?.enabled_profiles ?? 0} / ${data?.total_profiles ?? 0}`,
      icon: <CheckCircle2 className="h-4 w-4" />,
    },
    {
      label: "Runs (24h)",
      value: `${data?.runs_24h ?? 0} · ${data?.failures_24h ?? 0} failed`,
      icon: <Activity className="h-4 w-4" />,
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {tiles.map((t, i) => (
        <motion.div
          key={t.label}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.04 }}
        >
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {t.label}
              </CardTitle>
              <div className="text-muted-foreground">{t.icon}</div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-semibold">
                {isLoading ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  t.value
                )}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      ))}
    </div>
  );
}

// ----------------- Users table -----------------

function UsersTable() {
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState<AdminUser | null>(null);

  const { data = [], isLoading } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => api<AdminUser[]>("/api/admin/users"),
  });

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return data;
    return data.filter(
      (u) =>
        u.email.toLowerCase().includes(s) ||
        u.name.toLowerCase().includes(s) ||
        u.role.toLowerCase().includes(s) ||
        u.subscription.toLowerCase().includes(s),
    );
  }, [data, q]);

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle>Users</CardTitle>
            <CardDescription>
              Manage subscription, role and schedule for any user.
            </CardDescription>
          </div>
          <div className="relative w-full sm:w-72">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="Search users…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {isLoading ? (
          <Loader2 className="mx-auto h-5 w-5 animate-spin text-muted-foreground" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-muted-foreground">
                  <th className="py-2">User</th>
                  <th className="py-2">Role</th>
                  <th className="py-2">Plan</th>
                  <th className="py-2">Profile</th>
                  <th className="py-2">Last run</th>
                  <th className="py-2">Runs</th>
                  <th className="py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((u) => (
                  <tr key={u.id} className="border-t">
                    <td className="py-3">
                      <div className="font-medium">{u.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {u.email}
                      </div>
                    </td>
                    <td className="py-3">
                      {u.role === "admin" ? (
                        <Badge variant="warning">Admin</Badge>
                      ) : (
                        <Badge variant="secondary">User</Badge>
                      )}
                    </td>
                    <td className="py-3">
                      {u.subscription === "paid" ? (
                        <Badge variant="success">Pro</Badge>
                      ) : (
                        <Badge variant="secondary">Free</Badge>
                      )}
                    </td>
                    <td className="py-3">
                      {u.has_profile ? (
                        u.profile_enabled ? (
                          <Badge variant="success">Enabled</Badge>
                        ) : (
                          <Badge variant="secondary">Paused</Badge>
                        )
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="py-3">
                      {u.last_status ? (
                        <span className="flex items-center gap-2">
                          {u.last_status === "success" ? (
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                          ) : (
                            <XCircle className="h-3.5 w-3.5 text-red-500" />
                          )}
                          <span className="text-xs text-muted-foreground">
                            {formatDateTime(u.last_run_at)}
                          </span>
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="py-3">{u.run_count}</td>
                    <td className="py-3 text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setEditing(u)}
                      >
                        Edit
                      </Button>
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td
                      colSpan={7}
                      className="py-8 text-center text-sm text-muted-foreground"
                    >
                      No users found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>

      <EditUserDialog
        user={editing}
        onClose={() => setEditing(null)}
      />
    </Card>
  );
}

function EditUserDialog({
  user,
  onClose,
}: {
  user: AdminUser | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [subscription, setSubscription] = useState<"free" | "paid">("free");
  const [role, setRole] = useState<"user" | "admin">("user");
  const [profileEnabled, setProfileEnabled] = useState(true);

  useEffect(() => {
    if (user) {
      setSubscription(user.subscription === "paid" ? "paid" : "free");
      setRole(user.role === "admin" ? "admin" : "user");
      setProfileEnabled(user.profile_enabled ?? true);
    }
  }, [user]);

  const save = useMutation({
    mutationFn: () =>
      api(`/api/admin/users/${user!.id}`, {
        method: "PATCH",
        body: {
          subscription,
          role,
          profile_enabled: user!.has_profile ? profileEnabled : undefined,
        },
      }),
    onSuccess: () => {
      toast.success("User updated");
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      qc.invalidateQueries({ queryKey: ["admin-stats"] });
      onClose();
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.detail : "Failed"),
  });

  const remove = useMutation({
    mutationFn: () =>
      api(`/api/admin/users/${user!.id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("User deleted");
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      qc.invalidateQueries({ queryKey: ["admin-stats"] });
      onClose();
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.detail : "Failed"),
  });

  return (
    <Dialog open={!!user} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit user</DialogTitle>
          <DialogDescription>{user?.email}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Plan</Label>
            <Select
              value={subscription}
              onValueChange={(v) => setSubscription(v as "free" | "paid")}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="free">Free</SelectItem>
                <SelectItem value="paid">Pro</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Role</Label>
            <Select
              value={role}
              onValueChange={(v) => setRole(v as "user" | "admin")}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="user">User</SelectItem>
                <SelectItem value="admin">Admin</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {user?.has_profile && (
            <div className="flex items-center justify-between rounded-md border p-3">
              <div>
                <p className="text-sm font-medium">Schedule enabled</p>
                <p className="text-xs text-muted-foreground">
                  Toggle to pause their automated runs.
                </p>
              </div>
              <Switch
                checked={profileEnabled}
                onCheckedChange={setProfileEnabled}
              />
            </div>
          )}
        </div>

        <DialogFooter className="gap-2">
          <Button
            variant="destructive"
            onClick={() => {
              if (confirm(`Delete ${user?.email}? This cannot be undone.`)) {
                remove.mutate();
              }
            }}
            disabled={remove.isPending}
            className="mr-auto"
          >
            {remove.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              "Delete user"
            )}
          </Button>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => save.mutate()} disabled={save.isPending}>
            {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ----------------- Runs table -----------------

function RunsTable() {
  const { data = [], isLoading } = useQuery({
    queryKey: ["admin-runs"],
    queryFn: () => api<AdminRunLog[]>("/api/admin/runs?limit=50"),
    refetchInterval: 20_000,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent runs (all users)</CardTitle>
        <CardDescription>
          Latest 50 runs across the platform.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Loader2 className="mx-auto h-5 w-5 animate-spin text-muted-foreground" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-muted-foreground">
                  <th className="py-2">User</th>
                  <th className="py-2">When</th>
                  <th className="py-2">Status</th>
                  <th className="py-2">Attempts</th>
                  <th className="py-2">Error</th>
                </tr>
              </thead>
              <tbody>
                {data.map((r) => (
                  <tr key={r.id} className="border-t">
                    <td className="py-2 font-medium">{r.user_email ?? r.user_id}</td>
                    <td className="py-2">{formatDateTime(r.started_at)}</td>
                    <td className="py-2">
                      {r.status === "success" ? (
                        <Badge variant="success">Success</Badge>
                      ) : (
                        <Badge variant="destructive">{r.status}</Badge>
                      )}
                    </td>
                    <td className="py-2">{r.attempts}</td>
                    <td className="py-2 max-w-[28ch] truncate text-muted-foreground">
                      {r.error ?? "—"}
                    </td>
                  </tr>
                ))}
                {data.length === 0 && (
                  <tr>
                    <td
                      colSpan={5}
                      className="py-8 text-center text-sm text-muted-foreground"
                    >
                      No runs yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
