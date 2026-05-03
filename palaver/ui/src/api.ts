export interface AgentConfig {
    name: string;
    provider: string;
    model: string;
    description: string;
    prompt: string;
    temperature?: number | null;
    top_p?: number | null;
    thinking?: boolean | string | null;
}

export interface AgentInfo extends AgentConfig {
    id: string;
}

export interface Chatroom {
    id: string;
    name: string;
    agents: string[];
    limit_subagent_calls: boolean;
    max_subagent_calls: number;
    max_message_history: number;
    routing_type: RoutingType;
    created_at: string;
}

export type RoutingType = "autonomous" | "round_robin" | "single" | "incognito";

export interface ChatroomUpsertPayload {
    name: string;
    limit_subagent_calls: boolean;
    max_subagent_calls: number;
    max_message_history: number;
    routing_type: RoutingType;
}

export interface ProviderConfig {
    service: string;
    api_base?: string | null;
    api_key_env_var?: string | null;
    name: string;
}

export interface SimpleMessage {
    id: string;
    sender: string;
    recipients?: string[];
    role: "user" | "assistant" | "system";
    content: string;
    status?: "sending" | "error" | "sent";
}

export interface ChatMessage extends SimpleMessage {
    chatroom_id: string;
    timestamp: string;
}

const getApiBase = (): string => {
    // Check if the app is running in a packaged environment
    const api_host = import.meta.env.PALAVER_API_HOST
    const api_port = import.meta.env.PALAVER_API_PORT
    if ( api_host && api_port && import.meta.env.DEV) {
        return `${api_host}:${api_port}/api`;
    } else {
        // Production mode: Use the same origin as the frontend
        return `${window.location.origin}/api`;
    }
};

const API_BASE = getApiBase();

export async function fetchAgents(): Promise<AgentInfo[]> {
    const res = await fetch(`${API_BASE}/agents/`);
    if (!res.ok) throw new Error("Failed to fetch agents");
    return res.json();
}

export async function createAgent(agentData: AgentConfig): Promise<AgentInfo> {
    const res = await fetch(`${API_BASE}/agents/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(agentData)
    });
    if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(errData?.detail || "Failed to create agent");
    }
    return res.json();
}

export async function updateAgent(agentId: string, agentData: AgentConfig): Promise<AgentInfo> {
    const res = await fetch(`${API_BASE}/agents/${agentId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(agentData)
    });
    if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(errData?.detail || "Failed to update agent");
    }
    return res.json();
}

export async function deleteAgent(agentId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/agents/${agentId}`, {
        method: "DELETE"
    });
    if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(errData?.detail || "Failed to delete agent");
    }
}

export async function testAgent(agentData: AgentConfig): Promise< { response: string, error: null | string } > {
    const res = await fetch(`${API_BASE}/agents/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(agentData)
    });
    if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(errData?.detail || "Failed to test agent");
    }
    return res.json();
}

export async function fetchProviders(): Promise<ProviderConfig[]> {
    const res = await fetch(`${API_BASE}/providers/`);
    if (!res.ok) throw new Error("Failed to fetch providers");
    return res.json();
}

export async function createProvider(providerData: ProviderConfig): Promise<ProviderConfig> {
    const res = await fetch(`${API_BASE}/providers/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(providerData)
    });
    if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(errData?.detail || "Failed to create provider");
    }
    return res.json();
}

export async function updateProvider(providerName: string, providerData: ProviderConfig): Promise<ProviderConfig> {
    const res = await fetch(`${API_BASE}/providers/${providerName}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(providerData)
    });
    if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(errData?.detail || "Failed to update provider");
    }
    return res.json();
}

export async function deleteProvider(providerName: string): Promise<void> {
    const res = await fetch(`${API_BASE}/providers/${providerName}`, {
        method: "DELETE"
    });
    if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(errData?.detail || "Failed to delete provider");
    }
}

export async function fetchProviderModels(providerName: string): Promise<string[]> {
    const res = await fetch(`${API_BASE}/providers/${providerName}/models`);
    if (!res.ok) throw new Error(`Failed to fetch models for provider ${providerName}`);
    return res.json();
}

export async function fetchChatroom(chatroomId: string): Promise<Chatroom> {
    const res = await fetch(`${API_BASE}/chatrooms/${chatroomId}`);
    if (!res.ok) throw new Error("Failed to fetch chatroom");
    return res.json();
}

export async function fetchChatrooms(): Promise<Chatroom[]> {
    const res = await fetch(`${API_BASE}/chatrooms/`);
    if (!res.ok) throw new Error("Failed to fetch chatrooms");
    return res.json();
}

export async function createChatroom(payload: ChatroomUpsertPayload): Promise<Chatroom> {
    const res = await fetch(`${API_BASE}/chatrooms/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Failed to create chatroom");
    return res.json();
}

export async function updateChatroom(chatroomId: string, payload: Partial<ChatroomUpsertPayload>): Promise<Chatroom> {
    const res = await fetch(`${API_BASE}/chatrooms/${chatroomId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Failed to update chatroom");
    return res.json();
}

export async function deleteChatroom(chatroomId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/chatrooms/${chatroomId}`, {
        method: "DELETE"
    });
    if (!res.ok) throw new Error("Failed to delete chatroom");
    return res.json();
}

export async function fetchChatroomParticipants(chatroomId: string): Promise<string[]> {
    const res = await fetch(`${API_BASE}/chatrooms/${chatroomId}/agents`);
    if (!res.ok) throw new Error("Failed to fetch participants");
    return res.json();
}

export async function setChatroomParticipant(chatroomId: string, agentIds: string[]): Promise<void> {
    const res = await fetch(`${API_BASE}/chatrooms/${chatroomId}/agents`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_ids: agentIds })
    });
    if (!res.ok) throw new Error("Failed to add participant");
}

export async function setChatroomParticipants(chatroomId: string, agentIds: string[]): Promise<void> {
    return setChatroomParticipant(chatroomId, agentIds);
}

export async function addChatroomParticipant(chatroomId: string, agentId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/chatrooms/${chatroomId}/agents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: agentId })
    });
    if (!res.ok) throw new Error("Failed to add participant");
}

export async function removeChatroomParticipant(chatroomId: string, agentId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/chatrooms/${chatroomId}/agents/${agentId}`, {
        method: "DELETE"
    });
    if (!res.ok) throw new Error("Failed to remove participant");
}

export async function fetchChatroomMessages(chatroomId: string): Promise<ChatMessage[]> {
    const res = await fetch(`${API_BASE}/chatrooms/${chatroomId}/messages`);
    if (!res.ok) throw new Error("Failed to fetch messages");
    return res.json();
}


export async function fetchApiKeyNames(): Promise<string[]> {
    const res = await fetch(`${API_BASE}/keys`);
    if (!res.ok) throw new Error("Failed to fetch messages");
    return res.json();
}


export async function updateApiKey(name: string, value: string): Promise<void> {
    const res = await fetch(`${API_BASE}/keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, value })

    });
    if (!res.ok) throw new Error("Failed to fetch messages");
    return res.json();
}


export async function deleteApiKey(name: string): Promise<void> {
    const res = await fetch(`${API_BASE}/keys/${name}`, {
        method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to fetch messages");
    return res.json();
}
