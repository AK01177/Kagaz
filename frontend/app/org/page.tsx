import { redirect } from "next/navigation";

export default function OrgIndex() {
  redirect("/org/members");
}
