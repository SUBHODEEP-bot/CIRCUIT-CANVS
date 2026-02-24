export interface SessionUser {
  id: string;
  email: string;
  display_name?: string | null;
}

export interface SessionResponse {
  user: SessionUser | null;
  roles: string[];
}

async function request<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const res = await fetch(input, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    credentials: "include",
    ...init,
  });

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const message = (data && (data.error || data.message)) || "Request failed";
    throw new Error(message);
  }

  return data as T;
}

export function getSession() {
  return request<SessionResponse>("/api/auth/session");
}

export function login(email: string, password: string) {
  return request<{ user: SessionUser | null }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function signup(email: string, password: string, displayName?: string) {
  return request<{ user: SessionUser | null }>("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password, display_name: displayName }),
  });
}

export function logout() {
  return request<{ success: boolean }>("/api/auth/logout", {
    method: "POST",
  });
}

export function getProjects() {
  return request<any[]>("/api/projects");
}

export function createProject() {
  return request<any>("/api/projects", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function deleteProject(id: string) {
  return request<null>("/api/projects/" + id, {
    method: "DELETE",
  });
}

export function getModules() {
  return request<any[]>("/api/modules");
}

export function getModulePins(moduleId?: string) {
  const qs = moduleId ? `?module_id=${encodeURIComponent(moduleId)}` : "";
  return request<any[]>(`/api/module-pins${qs}`);
}

export function getProject(projectId: string) {
  return request<any[]>(`/api/projects/${projectId}`);
}

export function updateProject(projectId: string, body: any) {
  return request<any>(`/api/projects/${projectId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function uploadModuleImage(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch("/api/admin/module-images/upload", {
    method: "POST",
    body: formData,
    credentials: "include",
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || "Upload failed");
  }
  return data as { public_url: string };
}

export function adminCreateModule(body: any) {
  return request<any>("/api/admin/modules", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function adminUpdateModule(moduleId: string, body: any) {
  return request<any>(`/api/admin/modules/${moduleId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function adminDeleteModule(moduleId: string) {
  return request<null>(`/api/admin/modules/${moduleId}`, {
    method: "DELETE",
  });
}

export function adminCreatePins(moduleId: string, pins: any[]) {
  return request<any>(`/api/admin/module-pins/${moduleId}`, {
    method: "POST",
    body: JSON.stringify({ pins }),
  });
}

export function adminDeletePin(pinId: string) {
  return request<null>(`/api/admin/module-pins/${pinId}`, {
    method: "DELETE",
  });
}

export function adminLogin(name: string, password: string) {
  return request<{ success: boolean }>("/api/admin/login", {
    method: "POST",
    body: JSON.stringify({ name, password }),
  });
}

