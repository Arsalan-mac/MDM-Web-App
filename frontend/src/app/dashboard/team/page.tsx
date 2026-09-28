"use client";

import { OrganizationProfile, useOrganization } from "@clerk/nextjs";
import { Users } from "lucide-react";
import { Card, CardBody, EmptyState } from "@/components/ui";

export default function TeamPage() {
  const { organization, isLoaded } = useOrganization();

  if (!isLoaded) return null;

  if (!organization) {
    return (
      <Card>
        <CardBody>
          <EmptyState
            icon={<Users className="h-8 w-8" />}
            title="Select or create an organization"
            description="Use the switcher in the sidebar to pick a workspace before managing its team."
          />
        </CardBody>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink-900">Team</h1>
        <p className="mt-1 text-sm text-ink-500">
          Invite teammates to {organization.name} and manage their roles.
        </p>
      </div>

      <div className="overflow-hidden rounded-xl border border-ink-200 bg-white shadow-sm shadow-ink-900/[0.03] [&_.cl-rootBox]:w-full [&_.cl-card]:w-full [&_.cl-card]:shadow-none [&_.cl-card]:border-none">
        <OrganizationProfile
          routing="hash"
          appearance={{
            variables: {
              colorPrimary: "#4f46e5",
              borderRadius: "0.5rem",
              fontFamily: "var(--font-sans)",
            },
          }}
        />
      </div>
    </div>
  );
}
