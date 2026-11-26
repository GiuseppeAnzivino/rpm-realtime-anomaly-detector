import AppLayout from "../components/AppLayout.jsx";

const SECTIONS = [
  { id: "anomalies", label: "Real-time anomalies" },
  { id: "history", label: "History" },
]

export default function ClinicianPage() {
  return <AppLayout title="Clinician Area" sections={SECTIONS} />;
}