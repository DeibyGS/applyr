import { CalendarCheck } from "lucide-react";
import { ComingSoon } from "@/layout/ComingSoon";

export default function InterviewsPage() {
  return (
    <ComingSoon
      title="Interviews"
      message="applyr doesn't track interview dates or times yet — only whether an offer has reached the in-process stage. Real scheduling data needs its own update before this view can show anything honest."
      icon={CalendarCheck}
    />
  );
}
