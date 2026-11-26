import AppLayout from "../components/AppLayout.jsx";

const SECTIONS = [
  { id: "overview", label: "Overview" },
  { id: "accounts", label: "Clinician accounts" },
];

export default function AdminPage() {
  return <AppLayout title="Administrator Area" sections={SECTIONS} />;
}