import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  Clock,
  Download,
  ExternalLink,
  Eye,
  FileText,
  Loader2,
  PlayCircle,
  Save,
  Upload,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

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
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, ApiError, type Me, type RunLog } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { formatDateTime, timeToString } from "@/lib/utils";

export function DashboardPage() {
  const me = useMe();

  if (me.isLoading || !me.data) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <h1 className="text-2xl font-semibold tracking-tight">
          Welcome back, {me.data.user.name.split(" ")[0]}
        </h1>
        <p className="text-muted-foreground">
          Manage your account, Naukri credentials and update schedule.
        </p>
      </motion.div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          <ProfileCard me={me.data} />
          <ScheduleCard me={me.data} />
          <RunHistoryCard />
        </div>

        <div className="space-y-6">
          <AccountCard me={me.data} />
          <RunNowCard />
        </div>
      </div>
    </div>
  );
}

// -------------------- Account --------------------

function AccountCard({ me }: { me: Me }) {
  const [name, setName] = useState(me.user.name);
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: (payload: {
      name?: string;
      current_password?: string;
      new_password?: string;
    }) => api("/api/me", { method: "PATCH", body: payload }),
    onSuccess: () => {
      toast.success("Account updated");
      setCurrentPw("");
      setNewPw("");
      qc.invalidateQueries({ queryKey: ["me"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.detail : "Failed"),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Account</CardTitle>
        <CardDescription>Update your profile and password.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>Email</Label>
          <Input value={me.user.email} disabled />
        </div>
        <div className="space-y-2">
          <Label htmlFor="name">Name</Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="cur">Current password</Label>
            <Input
              id="cur"
              type="password"
              value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)}
              placeholder="••••••••"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="new">New password</Label>
            <Input
              id="new"
              type="password"
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              placeholder="Min 8 chars"
            />
          </div>
        </div>
        <Button
          onClick={() =>
            mutation.mutate({
              name: name !== me.user.name ? name : undefined,
              current_password: currentPw || undefined,
              new_password: newPw || undefined,
            })
          }
          disabled={mutation.isPending}
          className="w-full"
        >
          {mutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <Save className="h-4 w-4" /> Save changes
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}

// -------------------- Run Now --------------------

function RunNowCard() {
  const qc = useQueryClient();
  const mutation = useMutation({
    mutationFn: () =>
      api<{ detail: string }>("/api/me/run-now", { method: "POST" }),
    onSuccess: (res) => {
      toast.success(res.detail);
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["runs"] });
        qc.invalidateQueries({ queryKey: ["me"] });
      }, 2000);
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.detail : "Failed"),
  });

  return (
    <Card className="border-primary/30 bg-gradient-to-br from-primary/5 to-transparent">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <PlayCircle className="h-5 w-5 text-primary" /> Run now
        </CardTitle>
        <CardDescription>
          Trigger an update immediately. You'll get an email when it finishes.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="w-full"
        >
          {mutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <PlayCircle className="h-4 w-4" /> Start update
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}

// -------------------- Naukri profile --------------------

function ProfileCard({ me }: { me: Me }) {
  const qc = useQueryClient();
  const profile = me.profile;
  const [email, setEmail] = useState(profile?.naukri_email ?? "");
  const [password, setPassword] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  useEffect(() => {
    setEmail(profile?.naukri_email ?? "");
  }, [profile?.naukri_email]);

  // Fetch the authenticated resume PDF as a blob each time the preview opens,
  // then hand the iframe an object URL. Plain <a href="/api/me/resume"> would
  // miss the Authorization header and 401.
  useEffect(() => {
    if (!previewOpen) return;

    let cancelled = false;
    let createdUrl: string | null = null;

    (async () => {
      setPreviewLoading(true);
      setPreviewError(null);
      setPreviewUrl(null);
      try {
        const res = await api<Response>("/api/me/resume", { raw: true });
        if (!res.ok) {
          throw new ApiError(res.status, `Failed to load resume (${res.status})`);
        }
        const blob = await res.blob();
        if (cancelled) return;
        createdUrl = URL.createObjectURL(blob);
        setPreviewUrl(createdUrl);
      } catch (err) {
        if (!cancelled) {
          setPreviewError(
            err instanceof ApiError ? err.detail : "Failed to load resume",
          );
        }
      } finally {
        if (!cancelled) setPreviewLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [previewOpen]);

  const mutation = useMutation({
    mutationFn: async () => {
      const fd = new FormData();
      if (email) fd.append("naukri_email", email);
      if (password) fd.append("naukri_password", password);
      if (selectedFile) fd.append("resume", selectedFile);
      return api("/api/me/profile", { method: "PUT", formData: fd });
    },
    onSuccess: () => {
      toast.success("Naukri profile saved");
      setPassword("");
      setSelectedFile(null);
      if (fileRef.current) fileRef.current.value = "";
      qc.invalidateQueries({ queryKey: ["me"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.detail : "Failed"),
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Naukri credentials & resume</CardTitle>
            <CardDescription>
              Encrypted with Fernet. Only used to log in for your scheduled updates.
            </CardDescription>
          </div>
          {profile?.last_status && <StatusBadge status={profile.last_status} />}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="naukri_email">Naukri email</Label>
            <Input
              id="naukri_email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@naukri.com"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="naukri_password">
              Naukri password{" "}
              <span className="text-muted-foreground">
                (leave blank to keep existing)
              </span>
            </Label>
            <Input
              id="naukri_password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label>Resume (PDF, max 5 MB)</Label>
          <div className="flex flex-col gap-3 rounded-lg border border-dashed p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center rounded-md bg-muted">
                <FileText className="h-5 w-5 text-muted-foreground" />
              </div>
              <div className="text-sm">
                {selectedFile ? (
                  <span className="font-medium">{selectedFile.name}</span>
                ) : profile?.resume_filename ? (
                  <>
                    <p className="font-medium">{profile.resume_filename}</p>
                    <p className="text-xs text-muted-foreground">
                      Uploaded {formatDateTime(profile.resume_uploaded_at)}
                    </p>
                  </>
                ) : (
                  <span className="text-muted-foreground">No resume uploaded</span>
                )}
              </div>
            </div>
            <div className="flex gap-2">
              <input
                ref={fileRef}
                type="file"
                accept="application/pdf"
                className="hidden"
                onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
              />
              <Button
                type="button"
                variant="outline"
                onClick={() => fileRef.current?.click()}
              >
                <Upload className="h-4 w-4" /> Choose file
              </Button>
              {profile?.resume_filename && (
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setPreviewOpen(true)}
                >
                  <Eye className="h-4 w-4" /> Preview
                </Button>
              )}
            </div>
          </div>
        </div>

        <Button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
        >
          {mutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <Save className="h-4 w-4" /> Save profile
            </>
          )}
        </Button>
      </CardContent>

      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="flex h-[85vh] max-w-4xl flex-col gap-0 p-0">
          <DialogHeader className="border-b p-4 pr-10">
            <DialogTitle className="truncate">
              {profile?.resume_filename ?? "Resume"}
            </DialogTitle>
            {profile?.resume_uploaded_at && (
              <DialogDescription>
                Uploaded {formatDateTime(profile.resume_uploaded_at)}
              </DialogDescription>
            )}
          </DialogHeader>

          <div className="relative flex-1 bg-muted">
            {previewLoading && (
              <div className="absolute inset-0 flex items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            )}
            {previewError && !previewLoading && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-sm text-destructive">
                <XCircle className="h-6 w-6" />
                {previewError}
              </div>
            )}
            {previewUrl && !previewLoading && !previewError && (
              <iframe
                src={previewUrl}
                title="Resume preview"
                className="h-full w-full border-0"
              />
            )}
          </div>

          <div className="flex items-center justify-end gap-2 border-t p-3">
            {previewUrl && (
              <>
                <a href={previewUrl} target="_blank" rel="noreferrer">
                  <Button type="button" variant="outline">
                    <ExternalLink className="h-4 w-4" /> Open in new tab
                  </Button>
                </a>
                <a
                  href={previewUrl}
                  download={profile?.resume_filename ?? "resume.pdf"}
                >
                  <Button type="button">
                    <Download className="h-4 w-4" /> Download
                  </Button>
                </a>
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

// -------------------- Schedule --------------------

function ScheduleCard({ me }: { me: Me }) {
  const qc = useQueryClient();
  const profile = me.profile;
  const isPaid = me.user.subscription === "paid";

  const [mode, setMode] = useState<"once" | "twice">(profile?.schedule_mode ?? "once");
  const [time1, setTime1] = useState(timeToString(profile?.schedule_time1) || "09:30");
  const [time2, setTime2] = useState(timeToString(profile?.schedule_time2) || "13:45");
  const [enabled, setEnabled] = useState(profile?.enabled ?? true);

  useEffect(() => {
    if (!profile) return;
    setMode(profile.schedule_mode);
    setTime1(timeToString(profile.schedule_time1) || "09:30");
    setTime2(timeToString(profile.schedule_time2) || "13:45");
    setEnabled(profile.enabled);
  }, [profile]);

  const mutation = useMutation({
    mutationFn: async () => {
      const fd = new FormData();
      fd.append("schedule_mode", mode);
      fd.append("schedule_time1", time1);
      if (mode === "twice") fd.append("schedule_time2", time2);
      fd.append("enabled", String(enabled));
      return api("/api/me/profile", { method: "PUT", formData: fd });
    },
    onSuccess: () => {
      toast.success("Schedule saved");
      qc.invalidateQueries({ queryKey: ["me"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.detail : "Failed"),
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" /> Schedule
            </CardTitle>
            <CardDescription>
              Updates run in your local server timezone (IST by default).
            </CardDescription>
          </div>
          <div className="flex items-center gap-3">
            <Label htmlFor="enabled" className="text-sm">
              {enabled ? "Enabled" : "Paused"}
            </Label>
            <Switch
              id="enabled"
              checked={enabled}
              onCheckedChange={setEnabled}
            />
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div
          className={`grid gap-4 ${
            mode === "twice" ? "sm:grid-cols-3" : "sm:grid-cols-2"
          }`}
        >
          <div className="space-y-2">
            <Label>Frequency</Label>
            <Select
              value={mode}
              onValueChange={(v) => {
                if (v === "twice" && !isPaid) {
                  toast.error("Twice-daily updates are a Pro feature.");
                  return;
                }
                setMode(v as "once" | "twice");
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="once">Once a day</SelectItem>
                <SelectItem value="twice">
                  Twice a day {!isPaid && "(Pro)"}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="time1">First run</Label>
            <Input
              id="time1"
              type="time"
              value={time1}
              onChange={(e) => setTime1(e.target.value)}
            />
          </div>

          {mode === "twice" && (
            <div className="space-y-2">
              <Label htmlFor="time2">Second run</Label>
              <Input
                id="time2"
                type="time"
                value={time2}
                onChange={(e) => setTime2(e.target.value)}
              />
            </div>
          )}
        </div>

        <Button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
        >
          {mutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <Save className="h-4 w-4" /> Save schedule
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}

// -------------------- Run history --------------------

function RunHistoryCard() {
  const { data = [], isLoading } = useQuery({
    queryKey: ["runs"],
    queryFn: () => api<RunLog[]>("/api/me/runs"),
    refetchInterval: 15_000,
  });

  const rows = useMemo(() => data.slice(0, 10), [data]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent runs</CardTitle>
        <CardDescription>Your 10 most recent update attempts.</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Loader2 className="mx-auto h-5 w-5 animate-spin text-muted-foreground" />
        ) : rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No runs yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-muted-foreground">
                  <th className="py-2">When</th>
                  <th className="py-2">Status</th>
                  <th className="py-2">Attempts</th>
                  <th className="py-2">Error</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-t">
                    <td className="py-2">{formatDateTime(r.started_at)}</td>
                    <td className="py-2">
                      <StatusBadge status={r.status} />
                    </td>
                    <td className="py-2">{r.attempts}</td>
                    <td className="py-2 max-w-[20ch] truncate text-muted-foreground">
                      {r.error ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function StatusBadge({ status }: { status: string }) {
  if (status === "success")
    return (
      <Badge variant="success" className="gap-1">
        <CheckCircle2 className="h-3 w-3" /> Success
      </Badge>
    );
  if (status === "failed")
    return (
      <Badge variant="destructive" className="gap-1">
        <XCircle className="h-3 w-3" /> Failed
      </Badge>
    );
  return <Badge variant="secondary">{status}</Badge>;
}
