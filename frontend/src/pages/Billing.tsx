import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Check, CreditCard, Loader2, ShieldCheck, Sparkles } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api, ApiError, type Billing } from "@/lib/api";
import { cn, formatDateTime } from "@/lib/utils";

export function BillingPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["billing"],
    queryFn: () => api<Billing>("/api/me/billing"),
  });

  const subscribe = useMutation({
    mutationFn: () => api("/api/me/billing/subscribe", { method: "POST" }),
    onSuccess: () => {
      toast.success("Welcome to Pro! 🎉");
      qc.invalidateQueries({ queryKey: ["billing"] });
      qc.invalidateQueries({ queryKey: ["me"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.detail : "Failed"),
  });

  const cancel = useMutation({
    mutationFn: () => api("/api/me/billing/cancel", { method: "POST" }),
    onSuccess: () => {
      toast.success("Subscription cancelled");
      qc.invalidateQueries({ queryKey: ["billing"] });
      qc.invalidateQueries({ queryKey: ["me"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.detail : "Failed"),
  });

  if (isLoading || !data) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Billing</h1>
        <p className="text-muted-foreground">
          Manage your subscription and billing details.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CreditCard className="h-5 w-5" /> Current plan
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
          <div className="flex items-center gap-4">
            {data.subscription === "paid" ? (
              <Badge variant="success" className="px-3 py-1 text-sm">
                Pro
              </Badge>
            ) : (
              <Badge variant="secondary" className="px-3 py-1 text-sm">
                Free
              </Badge>
            )}
            <div>
              <p className="font-medium">
                {data.subscription === "paid" ? "Pro plan" : "Free plan"}
              </p>
              <p className="text-sm text-muted-foreground">
                {data.subscription === "paid"
                  ? `Active since ${formatDateTime(data.subscribed_at)}`
                  : "Upgrade anytime to unlock Pro features."}
              </p>
            </div>
          </div>
          {data.subscription === "paid" && (
            <Button
              variant="outline"
              onClick={() => cancel.mutate()}
              disabled={cancel.isPending}
            >
              {cancel.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Cancel subscription"
              )}
            </Button>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        {data.plans.map((plan, idx) => {
          const isCurrent = data.subscription === plan.id;
          const isPro = plan.id === "paid";
          return (
            <motion.div
              key={plan.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.05 }}
            >
              <Card
                className={cn(
                  "relative h-full overflow-hidden",
                  isPro && "border-primary/40 shadow-lg",
                )}
              >
                {isPro && (
                  <div className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-br from-primary/10 via-transparent to-transparent" />
                )}
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      {isPro ? (
                        <Sparkles className="h-4 w-4 text-primary" />
                      ) : (
                        <ShieldCheck className="h-4 w-4" />
                      )}
                      {plan.name}
                    </span>
                    {isCurrent && <Badge variant="outline">Current</Badge>}
                  </CardTitle>
                  <CardDescription>
                    <span className="text-3xl font-semibold text-foreground">
                      ₹{plan.price_inr}
                    </span>
                    <span className="text-muted-foreground"> / month</span>
                  </CardDescription>
                </CardHeader>

                <CardContent className="space-y-4">
                  <ul className="space-y-2 text-sm">
                    {plan.features.map((f) => (
                      <li key={f} className="flex items-start gap-2">
                        <Check className="mt-0.5 h-4 w-4 text-primary" />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>

                  {isPro &&
                    (isCurrent ? (
                      <Button className="w-full" disabled>
                        You're on Pro
                      </Button>
                    ) : (
                      <Button
                        className="w-full"
                        onClick={() => subscribe.mutate()}
                        disabled={subscribe.isPending}
                      >
                        {subscribe.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          "Upgrade to Pro"
                        )}
                      </Button>
                    ))}
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Payments</CardTitle>
          <CardDescription>
            This is a demo billing page — no real charges are made. Plug in
            Stripe or Razorpay in <code>/api/me/billing/subscribe</code> when
            ready to go live.
          </CardDescription>
        </CardHeader>
      </Card>
    </div>
  );
}
