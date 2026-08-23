import { useEffect, useState } from "react";
import { getJob, type JobDetail } from "@/api/jobs";

/**
 * Fetches the full detail for whichever job id is currently selected.
 * Shared by every page with an inline job-detail view (Office, Archive) so
 * the fetch-on-select effect isn't duplicated per page.
 */
export function useSelectedJob(selectedJobId: number | null) {
  const [selectedJob, setSelectedJob] = useState<JobDetail | null>(null);

  useEffect(() => {
    if (selectedJobId === null) {
      setSelectedJob(null);
      return;
    }
    getJob(selectedJobId).then(setSelectedJob);
  }, [selectedJobId]);

  return selectedJob;
}
