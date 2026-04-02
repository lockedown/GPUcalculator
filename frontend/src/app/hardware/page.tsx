import { fetchAllGPUs } from "@/lib/server-api";
import HardwareClient from "./hardware-client";

export const revalidate = 300;

export default async function HardwarePage() {
  const gpus = await fetchAllGPUs();
  return <HardwareClient initialGpus={gpus} />;
}
