export type Severity = "low" | "medium" | "high" | "critical";
export type IncidentStatus = "new" | "open" | "closed";
export type InvestigationStatus = "queued" | "running" | "completed" | "failed";

export interface Alert { id: string; source: string; source_event_id: string; event_type: string; severity: Severity; source_ip: string | null; destination_host: string | null; rule_name: string; observed_at: string; received_at: string; incident_id: string }
export interface Incident { id: string; title: string; description: string | null; severity: Severity; status: IncidentStatus; created_at: string; updated_at: string; closed_at: string | null }
export interface IncidentDetail extends Incident { alert_ids: string[] }
export interface Evidence { id: string; evidence_source: string; result: Record<string, unknown>; created_at: string }
export interface Investigation { id: string; incident_id: string; investigation_type: "suspicious_ip"; status: InvestigationStatus; attempt_count: number; source_ip: string; created_at: string; started_at: string | null; completed_at: string | null; next_attempt_at: string | null }
export interface InvestigationDetail extends Investigation { evidence: Evidence[] }
export interface Page<T> { items: T[]; page: number; page_size: number; total: number }
export type ResponseStatus = "proposed" | "approved" | "executing" | "executed" | "rejected" | "failed" | "reverted";
export interface AuditEvent { id: string; event_type: string; actor: string; from_status: string | null; to_status: string | null; metadata_json: Record<string, unknown>; created_at: string }
export interface ResponseAction { id: string; incident_id: string; investigation_id: string | null; action_type: "block_ip"; target_ip: string; status: ResponseStatus; proposed_by: string; decided_by: string | null; decided_at: string | null; decision_reason: string | null; created_at: string; updated_at: string; executed_at: string | null; execution_result: Record<string, unknown> | null; execution_error: string | null }
export interface ResponseActionDetail extends ResponseAction { audit_events: AuditEvent[] }
export interface LabBlockEntry { id: string; response_action_id: string; incident_id: string; ip_address: string; active: boolean; created_at: string; deactivated_at: string | null; execution_metadata: Record<string, unknown> }
export interface LabBlocklistPage extends Page<LabBlockEntry> { simulation: true }

export class ApiError extends Error { constructor(message: string, public readonly status?: number) { super(message); } }
const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? "/api/v1").replace(/\/$/, "");

export class SoarApi {
  constructor(private readonly analystKey: string) {}
  private async request<T>(path: string, options: { method?: "POST"; body?: object; signal?: AbortSignal } = {}): Promise<T> {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 10_000);
    const abort = () => controller.abort();
    options.signal?.addEventListener("abort", abort, { once: true });
    try {
      const response = await fetch(`${baseUrl}${path}`, { method: options.method, headers: { "X-API-Key": this.analystKey, ...(options.body ? { "Content-Type": "application/json" } : {}) }, body: options.body ? JSON.stringify(options.body) : undefined, signal: controller.signal });
      if (!response.ok) {
        let message = response.status === 401 ? "Authentication failed. Check the analyst API key." : `Request failed (${response.status}).`;
        try { message = (await response.json() as { detail?: string }).detail ?? message; } catch { /* response is not JSON */ }
        throw new ApiError(message, response.status);
      }
      return response.json() as Promise<T>;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (error instanceof DOMException && error.name === "AbortError") throw new ApiError("Request timed out. Is the API running?");
      throw new ApiError("Could not reach the API. Check the local backend connection.");
    } finally { window.clearTimeout(timeout); options.signal?.removeEventListener("abort", abort); }
  }
  incidents(page = 1, status?: IncidentStatus) { return this.request<Page<Incident>>(`/incidents?page=${page}&page_size=25${status ? `&incident_status=${status}` : ""}`); }
  incident(id: string) { return this.request<IncidentDetail>(`/incidents/${id}`); }
  alert(id: string) { return this.request<Alert>(`/alerts/${id}`); }
  alerts() { return this.request<Page<Alert>>("/alerts?page=1&page_size=100"); }
  investigations(page = 1, status?: InvestigationStatus) { return this.request<Page<Investigation>>(`/investigations?page=${page}&page_size=25${status ? `&investigation_status=${status}` : ""}`); }
  investigation(id: string) { return this.request<InvestigationDetail>(`/investigations/${id}`); }
  responseActions(page = 1, status?: ResponseStatus) { return this.request<Page<ResponseAction>>(`/response-actions?page=${page}&page_size=25${status ? `&action_status=${status}` : ""}`); }
  responseAction(id: string) { return this.request<ResponseActionDetail>(`/response-actions/${id}`); }
  propose(incidentId: string, investigationId: string, targetIp: string) { return this.request<ResponseAction>(`/incidents/${incidentId}/response-actions`, { method: "POST", body: { investigation_id: investigationId, target_ip: targetIp } }); }
  decide(id: string, decision: "approve" | "reject", reason?: string) { return this.request<ResponseAction>(`/response-actions/${id}/${decision}`, { method: "POST", body: { reason: reason || null } }); }
  revert(id: string, reason?: string) { return this.request<ResponseAction>(`/response-actions/${id}/revert`, { method: "POST", body: { reason: reason || null } }); }
  blocklist(page = 1, active?: boolean) { return this.request<LabBlocklistPage>(`/lab/blocklist?page=${page}&page_size=25${active === undefined ? "" : `&active=${active}`}`); }
}
