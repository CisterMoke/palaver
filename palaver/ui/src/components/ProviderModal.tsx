import { useState, useEffect } from "preact/hooks";
import type { TargetedEvent } from "preact";
import { createProvider, updateProvider, fetchApiKeyNames, deleteApiKey } from "../api";
import type { ProviderConfig } from "../api";
import ApiKeyModal from "./ApiKeyModal";
import icons from "./../assets/feathericons.svg?no-inline"

interface ProviderModalProps {
  existingProviders: string[];
  onClose: () => void;
  onSuccess: (newProvider: string) => void;
  existingProvider?: ProviderConfig;
}

export default function ProviderModal({ existingProviders, onClose, onSuccess, existingProvider }: ProviderModalProps) {
  const [service, setService] = useState(existingProvider?.service || "openai");
  const [apiBase, setApiBase] = useState(existingProvider?.api_base || null);
  const [name, setName] = useState(existingProvider?.name || "");
  const [loading, setLoading] = useState(false);
  const [actionSuccess, setActionSuccess] = useState<{ success: boolean, message: string } | null>(null);
  const [loadingApiKeys, setLoadingApiKeys] = useState(true);
  const [availableApiKeys, setAvailableApiKeys] = useState<string[]>([])
  const [apiKeyModalMode, setApiKeyModalMode] = useState<"create" | "edit" | null>(null);
  
  const isNameTaken = !existingProvider && existingProviders.includes(name.trim());

  const keyNameFromEnvVar = function (envVar?: string | null) {
    if (!envVar) {
      return null;
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
    if (!name.trim()) {
      setActionSuccess({success: false, message: "Name is required"});
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
        api_base: Boolean(apiBase) ? apiBase!.trim() : null,
        api_key_env_var: Boolean(apiKeyName) ? (apiKeyName!.trim() + "_API_KEY") : null,
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
    <div className="fixed inset-0 flex items-start justify-center z-60 p-4">
      <div className="bg-black/50 h-full rounded-lg w-125 max-w-[90vw] shadow-xl max-h-[calc(100vh-2rem)] overflow-hidden"></div>
      <div className="bg-white absolute rounded-lg p-6 w-125 max-w-[90vw] shadow-xl max-h-[calc(100vh-2rem)] min-h-51 flex flex-col">
        <div className="shrink-0">
          <h2 className="text-xl font-bold">{existingProvider ? 'Edit Provider' : 'Create New Provider'}</h2>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 flex flex-col overflow-hidden min-h-32" autocomplete="off">
          <div className="flex-1 overflow-y-auto flex flex-col gap-4 py-2 px-1">
            {actionSuccess && (
              <div className={`p-3 border rounded text-sm ${
                actionSuccess.success
                  ? "bg-green-100 border-green-300 text-green-700" 
                  : "bg-red-100 border border-red-300 text-red-700"
              }`}>
                {actionSuccess.message}
              </div>
            )}

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
                autocomplete="off"
                required
                disabled={!!existingProvider}
              />
              {isNameTaken && (
                <p className="text-red-500 text-xs mt-1">This provider name already exists.</p>
              )}
            </div>

            <div>
              <label for="api-base-url-input" className="block text-sm font-medium text-gray-700 mb-1">API Base URL</label>
              <input
                id="api-base-url-input"
                type="url"
                className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                value={apiBase == null ? "" : apiBase}
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
                <label for="api-key-name-options" className="block relative text-sm font-medium text-gray-700 mb-1">
                  <span>API Key Env Var</span>
                  {apiKeyName && apiKeyName !== "new" && (
                    <div className="flex items-center gap-1 absolute right-0 top-0 h-full align-middle">
                      <span onClick={() => {setApiKeyModalMode("edit"); setActionSuccess(null)}} className="text-gray-500 hover:text-blue-500" title="Edit API Key">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4">
                          <use href={`${icons}#edit`} />
                        </svg>
                      </span>
                      <span onClick={handleDeleteApiKey} className="text-gray-500 hover:text-red-500" title="Delete API Key">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4">
                          <use href={`${icons}#trash-2`} />
                        </svg>
                      </span>
                    </div>
                  )}
                </label>
                <select
                id="api-key-name-options"
                className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                value={apiKeyName == null ? "" : apiKeyName}
                onChange={(e) => {
                  setActionSuccess(null);
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
                    {apiKeyName != null && !availableApiKeys.includes(apiKeyName) && <option value={apiKeyName}>{apiKeyName}</option>}
                    {availableApiKeys.map(k => (
                      <option value={k}>{k}</option>
                    ))}
                    <option value="new" className="font-bold text-blue-600">+ new</option>
                  </>
                )}
                </select>
              </div>
            </div>
          </div>
          <div className="shrink-0 flex justify-end gap-3 pt-2 border-t border-gray-200">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded"
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 disabled:opacity-50"
              disabled={loading || isNameTaken}
            >
              {loading ? "Saving..." : (existingProvider ? "Save Provider" : "Create Provider")}
            </button>
          </div>
        </form>
      </div>
      {apiKeyModalMode && (
        <ApiKeyModal
          selectedApiKey={apiKeyModalMode === "edit" ? apiKeyName! : ""}
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
