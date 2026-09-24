import Link from "next/link";
import {
  SignInButton,
  SignUpButton,
  SignedIn,
  SignedOut,
  UserButton,
  OrganizationSwitcher,
} from "@clerk/nextjs";

export default function Home() {
  return (
    <main style={{ padding: "3rem", maxWidth: 640, margin: "0 auto" }}>
      <h1>MDM Web App</h1>
      <p>Multi-tenant data cleansing &amp; SAP migration platform.</p>

      <SignedOut>
        <SignInButton mode="modal">
          <button>Sign in</button>
        </SignInButton>{" "}
        <SignUpButton mode="modal">
          <button>Sign up</button>
        </SignUpButton>
      </SignedOut>

      <SignedIn>
        <p>
          <Link href="/dashboard">Go to dashboard</Link>
        </p>
        <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
          <UserButton />
          {/* Creating/selecting an org here is what makes it the active tenant
              for subsequent API calls - see app/api/deps.py::get_current_tenant. */}
          <OrganizationSwitcher hidePersonal createOrganizationMode="modal" />
        </div>
      </SignedIn>
    </main>
  );
}
