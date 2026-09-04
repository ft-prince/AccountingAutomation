"use client";

import { UserPlus, Users } from "lucide-react";
import { useState } from "react";
import { ConfirmDialog } from "@/components/primitives/confirm-dialog";
import { EmptyState } from "@/components/primitives/empty-state";
import { Field } from "@/components/primitives/field";
import { NativeSelect } from "@/components/primitives/native-select";
import { QueryState } from "@/components/primitives/query-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/hooks/use-toast";
import { ICON_STROKE } from "@/lib/constants";
import { useInviteMember, useMembers, useRemoveMember, useUpdateMemberRole } from "@/lib/settings";
import { toastApiError } from "@/lib/toast";
import type { MemberRole, Membership } from "@/lib/types";

export const MEMBER_ROLES: readonly MemberRole[] = ["owner", "accountant", "reviewer", "viewer"];
const DEFAULT_ROLE: MemberRole = "viewer";

function InviteForm() {
  const invite = useInviteMember();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<MemberRole>(DEFAULT_ROLE);
  const submit = () =>
    invite.mutate(
      { email: email.trim(), role },
      {
        onSuccess: () => {
          toast({ title: "Member added" });
          setEmail("");
        },
        onError: (error) => toastApiError(error, "Could not add member"),
      },
    );
  return (
    <form
      className="flex flex-wrap items-end gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <Field id="invite-email" label="Email" required>
        <Input id="invite-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="w-64" />
      </Field>
      <Field id="invite-role" label="Role">
        <NativeSelect id="invite-role" value={role} onChange={(event) => setRole(event.target.value as MemberRole)}>
          {MEMBER_ROLES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </NativeSelect>
      </Field>
      <Button type="submit" disabled={email.trim() === "" || invite.isPending}>
        <UserPlus size={16} strokeWidth={ICON_STROKE} aria-hidden /> {invite.isPending ? "Adding…" : "Add member"}
      </Button>
    </form>
  );
}

export function MembersTab({ isOwner, currentEmail }: { isOwner: boolean; currentEmail: string | undefined }) {
  const members = useMembers();
  const updateRole = useUpdateMemberRole();
  const remove = useRemoveMember();
  const [removing, setRemoving] = useState<Membership | null>(null);

  const changeRole = (member: Membership, role: MemberRole) =>
    updateRole.mutate(
      { id: member.id, role },
      { onSuccess: () => toast({ title: `${member.email} is now ${role}` }), onError: (error) => toastApiError(error, "Could not change role") },
    );

  const confirmRemove = () => {
    if (!removing) return;
    remove.mutate(removing.id, {
      onSuccess: () => {
        toast({ title: "Member removed" });
        setRemoving(null);
      },
      onError: (error) => toastApiError(error, "Could not remove member"),
    });
  };

  return (
    <div className="space-y-4">
      {isOwner ? <InviteForm /> : <p className="text-sm text-muted">Only owners can add members or change roles.</p>}
      <QueryState isPending={members.isPending} error={members.error} onRetry={() => void members.refetch()}>
        {members.data?.length === 0 ? (
          <EmptyState icon={Users} title="No members" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Since</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.data?.map((member) => (
                <TableRow key={member.id}>
                  <TableCell>
                    {member.email} {member.email === currentEmail && <span className="text-xs text-muted">(you)</span>}
                  </TableCell>
                  <TableCell className="text-muted">{member.full_name || "—"}</TableCell>
                  <TableCell>
                    {isOwner ? (
                      <NativeSelect aria-label={`Role for ${member.email}`} value={member.role ?? DEFAULT_ROLE} onChange={(event) => changeRole(member, event.target.value as MemberRole)}>
                        {MEMBER_ROLES.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </NativeSelect>
                    ) : (
                      member.role
                    )}
                  </TableCell>
                  <TableCell className="text-muted">{member.created_at.slice(0, 10)}</TableCell>
                  <TableCell className="text-right">
                    {isOwner && member.email !== currentEmail && (
                      <Button variant="ghost" size="sm" className="text-danger" onClick={() => setRemoving(member)}>
                        Remove
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </QueryState>
      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(open) => !open && setRemoving(null)}
        title={`Remove ${removing?.email ?? ""}?`}
        description="They lose access immediately. The last owner cannot be removed."
        confirmLabel="Remove"
        destructive
        isPending={remove.isPending}
        onConfirm={confirmRemove}
      />
    </div>
  );
}
