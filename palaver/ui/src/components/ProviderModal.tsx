import { useState, useEffect } from "preact/hooks";
import type { TargetedEvent } from "preact";
import { createProvider, updateProvider, fetchApiKeyNames, deleteApiKey } from "../api";
import type { ProviderConfig } from "../api";
import ApiKeyModal from "./ApiKeyModal";

interface ProviderModalProps {
  existingProviders: string[];
  onClose: () => void;
  onSuccess: (newProvider: string) => void;
  existingProvider?: ProviderConfig;
}

export default function ProviderModal({ existingProviders, onClose, onSuccess, existingProvider }: ProviderModalProps) {
  const [service, setService] = useState(existingProvider?.service || "openai");
  const [apiBase, setApiBase] = useState(existingProvider?.api_base || "");
  const [name, setName] = useState(existingProvider?.name || "");
  const [loading, setLoading] = useState(false);
  const [actionSuccess, setActionSuccess] = useState<{ success: boolean, message: string } | null>(null);
  const [loadingApiKeys, setLoadingApiKeys] = useState(true);
  const [availableApiKeys, setAvailableApiKeys] = useState<string[]>([])
  const [apiKeyModalMode, setApiKeyModalMode] = useState<"create" | "edit" | null>(null);
  
  const isNameTaken = !existingProvider && existingProviders.includes(name.trim());

  const keyNameFromEnvVar = (envVar?: string) => {
    if (!envVar) {
      return ""
    }
    if (!envVar.endsWith("_API_KEY")) {
      return envVar;
    }
    return envVar.slice(0, -("_API_KEY".length));
  };
  
  const [apiKeyName, setApiKeyName] = useState(keyNameFromEnvVar(existingProvider?.api_key_env_var));

  useEffect(() => {
    async function loadApiKeyNames() {
      try {
        const keyNames = await fetchApiKeyNames();
        setAvailableApiKeys(keyNames);
        
        if (keyNames.length > 0 && !apiKeyName) {
          setApiKeyName(keyNames[0]);
        }
      } catch (err) {
        console.error("Failed to load API key list.", err);
        setActionSuccess({success: false, message: "Failed to load API key list."});
      } finally {
        setLoadingApiKeys(false);
      }
    }
    loadApiKeyNames();
  }, []);

  const handleSubmit = async (e: TargetedEvent) => {
    e.preventDefault();
    if (!name.trim() || !apiBase.trim()) {
      setActionSuccess({success: false, message: "Name and API Base URL are required"});
      return;
    }

    if (isNameTaken) {
      setActionSuccess({success: false, message: "Provider name already exists"});
      return;
    }

    setLoading(true);
    setActionSuccess(null);

    try {
      const data: ProviderConfig = {
        service: service,
        api_base: apiBase.trim(),
        api_key_env_var: apiKeyName.trim() + "_API_KEY",
        name: name.trim(),
      };
      
      if (existingProvider) {
        await updateProvider(existingProvider.name, data);
      } else {
        await createProvider(data);
      }
      
      onSuccess(data.name);
      onClose();
    } catch (err: any) {
      setActionSuccess({success: false, message: err.message || "Failed to create provider"});
    } finally {
      setLoading(false);
    }
  };


  const handleDeleteApiKey = async () => {
    if (!apiKeyName || apiKeyName === "new") return;
    if (confirm(`Are you sure you want to delete the API key '${apiKeyName}'?`)) {
      try {
        await deleteApiKey(apiKeyName);
        const keyNames = await fetchApiKeyNames();
        setAvailableApiKeys(keyNames);
        setApiKeyName(keyNames.length > 0 ? keyNames[0] : "");
        setActionSuccess({success: true, message: "Delete successful"})
      } catch (err: any) {
        setActionSuccess({success: false, message: err.message || "Failed to delete API key"});
      }
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-60">
      <div className="bg-white rounded-lg p-6 w-125 max-w-[90vw] shadow-xl">
        <h2 className="text-xl font-bold mb-4">{existingProvider ? 'Edit Provider' : 'Create New Provider'}</h2>
        
        {actionSuccess && (
          <div className={`mb-4 p-3 border rounded text-sm ${
            actionSuccess.success
              ? "bg-green-100 border-green-300 text-green-700" 
              : "bg-red-100 border border-red-300 text-red-700"
          }`}>
            {actionSuccess.message}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4" autocomplete="off">
          <div>
            <label for="provider-name-input" className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
            <input
              id="provider-name-input"
              type="text"
              className={`w-full border rounded p-2 focus:ring-2 focus:outline-none ${
                isNameTaken 
                  ? "border-red-500 focus:ring-red-500 bg-red-50" 
                  : "focus:ring-blue-500"
              } ${existingProvider ? "bg-gray-100 text-gray-500" : ""}`}
              value={name}
              onChange={(e) => setName(e.currentTarget.value)}
              placeholder="e.g. openai"
              required
              disabled={!!existingProvider}
            />
            {isNameTaken && (
              <p className="text-red-500 text-xs mt-1">This provider name already exists.</p>
            )}
          </div>

          <div>
            <label for="api-base-url-input" className="block text-sm font-medium text-gray-700 mb-1">API Base URL *</label>
            <input
              id="api-base-url-input"
              type="url"
              className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              value={apiBase}
              onChange={(e) => setApiBase(e.currentTarget.value)}
              placeholder="e.g. https://api.openai.com/v1"
            />
          </div>

          <div className="flex gap-4">
            <div className="flex-1">
              <label for="api-style-options" className="block text-sm font-medium text-gray-700 mb-1">API Style</label>
              <select
                id="api-style-options"
                className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                value={service}
                onChange={(e) => setService(e.currentTarget.value)}
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="bedrock">Bedrock</option>
                <option value="cohere">Cohere</option>
                <option value="google">Google</option>
                <option value="groq">Groq</option>
                <option value="huggingface">Huggingface</option>
                <option value="mistral">Mistral</option>
              </select>
            </div>
            <div className="flex-1">
              <label for="api-key-name-options" className="block text-sm font-medium text-gray-700 mb-1">API Key Env Var</label>
              {apiKeyName && apiKeyName !== "new" && (
                <div className="flex items-center gap-1">
                  <button type="button" onClick={() => {setApiKeyModalMode("edit"); setActionSuccess(null)}} className="text-gray-400 hover:text-blue-500" title="Edit API Key">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                    </svg>
                  </button>
                  <button type="button" onClick={handleDeleteApiKey} className="text-gray-400 hover:text-red-500" title="Delete API Key">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              )}
              <select
                id="api-key-name-options"
                className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                value={apiKeyName}
                onChange={(e) => {
                  if (e.currentTarget.value === "new") {
                    setApiKeyModalMode("create");
                  } else {
                    setApiKeyName(e.currentTarget.value);
                  }
                }}
              >
              {loadingApiKeys ? (
                <option value="">Loading API Keys...</option>
              ) : (
                <>
                  {!availableApiKeys.includes(apiKeyName) && <option value={apiKeyName}>{apiKeyName}</option>}
                  {availableApiKeys.map(k => (
                    <option value={k}>{k}</option>
                  ))}
                  <option value="new" className="font-bold text-blue-600">+ new</option>
                </>
              )}
              </select>

            </div>
          </div>

          <div className="flex justify-end gap-3 mt-4 pt-4 border-t">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded"
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              disabled={loading || isNameTaken}
            >
              {loading ? "Saving..." : (existingProvider ? "Save Provider" : "Create Provider")}
            </button>
          </div>
        </form>
      </div>
      {apiKeyModalMode && (
        <ApiKeyModal
          selectedApiKey={apiKeyModalMode === "edit" ? apiKeyName : ""}
          existingApiKeys={availableApiKeys}
          onClose={() => setApiKeyModalMode(null)}
          onSuccess={async (newApiKeyName) => {
            try {
              const keyNames = await fetchApiKeyNames();
              setAvailableApiKeys(keyNames);
              setApiKeyName(newApiKeyName);
            } catch (err) {
              console.error("Failed to reload api keys", err);
            }
          }}
        />
      )}
    </div>
  );
}
