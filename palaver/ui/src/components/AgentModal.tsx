import { useState, useEffect } from "preact/hooks";
import type { TargetedEvent } from "preact";
import { createAgent, updateAgent, fetchProviders, fetchProviderModels, testAgent, deleteProvider } from "../api";
import type { ProviderConfig, AgentInfo } from "../api";
import ProviderModal from "./ProviderModal";
import icons from "./../assets/feathericons.svg?no-inline"

interface AgentModalProps {
  onClose: () => void;
  onSuccess: () => void;
  existingAgent?: AgentInfo | null;
}

export default function AgentModal({ onClose, onSuccess, existingAgent }: AgentModalProps) {
  const [name, setName] = useState(existingAgent?.name || "");
  const [description, setDescription] = useState(existingAgent?.description || "");
  const [systemPrompt, setSystemPrompt] = useState(existingAgent?.prompt || "");
  const [temperature, setTemperature] = useState(existingAgent?.temperature);
  const [topP, setTopP] = useState(existingAgent?.top_p);
  const [thinking, setThinking] = useState(existingAgent?.thinking);
  const [provider, setProvider] = useState(existingAgent?.provider || "");
  const [model, setModel] = useState(existingAgent?.model || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean, message: string } | null>(null);

  const [availableProviders, setAvailableProviders] = useState<ProviderConfig[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(true);
  const [providerModalMode, setProviderModalMode] = useState<"create" | "edit" | null>(null);

  const [modelsCache, setModelsCache] = useState<Record<string, string[]>>({});
  const [loadingModels, setLoadingModels] = useState(false);

  useEffect(() => {
    async function loadProviders() {
      try {
        const providers = await fetchProviders();
        setAvailableProviders(providers);
        
        if (providers.length > 0 && !provider) {
          setProvider(providers[0].name);
        }
      } catch (err) {
        console.error("Failed to load providers", err);
        setError("Failed to load providers list.");
      } finally {
        setLoadingProviders(false);
      }
    }
    loadProviders();
  }, []);

  useEffect(() => {
    if (!provider) return;
    
    // If we already have models for this provider, no need to fetch again
    if (modelsCache[provider]) return;

    async function loadModels() {
      setLoadingModels(true);
      try {
        const models = await fetchProviderModels(provider);
        setModelsCache(prev => ({ ...prev, [provider]: models }));
      } catch (err) {
        console.error(`Failed to load models for ${provider}`, err);
      } finally {
        setLoadingModels(false);
      }
    }
    
    loadModels();
  }, [provider]);

  const handleTest = async () => {
    if (!name.trim()) {
      setError("Name is required to test");
      return;
    }

    setTesting(true);
    setTestResult(null);
    setError("");

    try {
      const result = await testAgent({
        name,
        description,
        prompt: systemPrompt,
        temperature,
        top_p: topP,
        thinking,
        provider,
        model
      });
      const success = result.error == null;
      setTestResult({ success: success, message: success ? result.response : result.error || "NOK"});
    } catch (err: any) {
      setTestResult({ success: false, message: err.message || "NOK" });
    } finally {
      setTesting(false);
    }
  };

  const handleSubmit = async (e: TargetedEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Name is required");
      return;
    }

    setLoading(true);
    setError("");

    try {
      if (existingAgent) {
        await updateAgent(existingAgent.id, {
          name: existingAgent.name, // Keep original name/id
          description,
          prompt: systemPrompt,
          temperature,
          top_p: topP,
          thinking,
          provider,
          model
        });
      } else {
        await createAgent({
          name,
          description,
          prompt: systemPrompt,
          temperature,
          top_p: topP,
          thinking,
          provider,
          model
        });
      }
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to save agent");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteProvider = async () => {
    if (!provider || provider === "new") return;
    if (confirm(`Are you sure you want to delete the provider '${provider}'?`)) {
      try {
        await deleteProvider(provider);
        const providers = await fetchProviders();
        setAvailableProviders(providers);
        setProvider(providers.length > 0 ? providers[0].name : "");
      } catch (err: any) {
        setError(err.message || "Failed to delete provider");
      }
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-start justify-center z-50 p-4">
      <div className="bg-white absolute rounded-lg p-6 w-125 h-full max-w-[90vw] shadow-xl max-h-[calc(100vh-2rem)] min-h-fit flex flex-col">
        <div className="shrink-0">
          <h2 className="text-xl font-bold">{existingAgent ? 'Edit Agent' : 'Create New Agent'}</h2>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 flex flex-col overflow-hidden min-h-32" autocomplete="off">
          <div className="flex-1 overflow-y-auto flex flex-col gap-4 py-2 px-1">
            {error && (
              <div className="p-3 bg-red-100 border border-red-300 text-red-700 rounded text-sm">
                {error}
              </div>
            )}

            {testResult && (
              <div className={`p-3 border rounded text-sm ${
                testResult.success
                  ? "bg-green-100 border-green-300 text-green-700" 
                  : "bg-red-100 border border-red-300 text-red-700"
              }`}>
                <span className="font-bold">{testResult.success ? "Test Passed: " : "Test Failed: "}</span>
                {testResult.message}
              </div>
            )}

          <div>
            <label for="agent-name-input" className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
            <input
              id="agent-name-input"
              type="text"
              className={`w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none ${existingAgent ? "bg-gray-100 text-gray-500" : ""}`}
              value={name}
              onChange={(e) => setName(e.currentTarget.value)}
              placeholder="e.g. CodeHelper"
              required
              disabled={!!existingAgent}
            />
          </div>

          <div>
            <label for="agent-description-input" className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <input
              id="agent-description-input"
              type="text"
              className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              value={description}
              onChange={(e) => setDescription(e.currentTarget.value)}
              placeholder="What does this agent do?"
            />
          </div>

          <div>
            <label for="agent-system-prompt-input" className="block text-sm font-medium text-gray-700 mb-1">System Prompt</label>
            <textarea
              id="agent-system-prompt-input"
              className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none min-h-25"
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.currentTarget.value)}
              placeholder="You are a helpful coding assistant..."
            />
          </div>
          <div className="flex flex-row justify-evenly">
            <div>
              <label for="agent-temperature-input" className="block text-sm font-medium text-gray-700 mb-1">Temperature</label>
              <input
                id="agent-temperature-input"
                type="number"
                step="0.1"
                min="0.1"
                max="1.0"
                className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                value={temperature === null ? undefined : temperature}
                onChange={(e) => setTemperature(+e.currentTarget.value == 0 ? null : +e.currentTarget.value)}
              />
            </div>

            <div>
              <label for="agent-top_p-input" className="block text-sm font-medium text-gray-700 mb-1">Top P</label>
              <input
                id="agent-top_p-input"
                type="number"
                step="0.1"
                min="0.1"
                max="1.0"
                className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                value={topP === null ? undefined : topP}
                onChange={(e) => setTopP(+e.currentTarget.value == 0 ? null : +e.currentTarget.value)}
              />
            </div>

            <div>
              <label for="agent-thinking-input" className="block text-sm font-medium text-gray-700 mb-1">Thinking</label>
              <select
                id="agent-thinking-input"
                className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                value={
                  thinking === null ? "none"
                  : thinking === false ? "off"
                  : thinking === true ? "on"
                  : thinking
                }
                onChange={(e) => setThinking(
                  e.currentTarget.value === "none" ? null :
                  e.currentTarget.value === "off" ? false :
                  e.currentTarget.value === "on" ? true :
                  e.currentTarget.value
                )}
              >
                <option value={"none"}>--none--</option>
                <option value={"off"}>off</option>
                <option value={"on"}>on</option>
                <option value={"minimal"}>minimal</option>
                <option value={"low"}>low</option>
                <option value={"medium"}>medium</option>
                <option value={"high"}>high</option>
                <option value={"xhigh"}>xhigh</option>
              </select>
            </div>
          </div>
          <div className="flex gap-4">
            <div className="flex-1">
              <label for="provider-options" className="block relative text-sm font-medium text-gray-700 mb-1">
                <span>Provider</span>
                {provider && provider !== "new" && (
                  <div className="flex items-center gap-1 absolute right-0 top-0 h-full align-middle">
                    <span onClick={() => setProviderModalMode("edit")} className="hover:text-blue-500" title="Edit Provider">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4">
                        <use href={`${icons}#edit`} />
                      </svg>
                    </span>
                    <span onClick={handleDeleteProvider} className="hover:text-red-500" title="Delete Provider">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4">
                        <use href={`${icons}#trash-2`} />
                      </svg>
                    </span>
                  </div>
                )}
              </label>
              <select
                id="provider-options"
                className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                value={provider}
                onChange={(e) => {
                  if (e.currentTarget.value === "new") {
                    setProviderModalMode("create");
                  } else {
                    setProvider(e.currentTarget.value);
                  }
                }}
                disabled={loadingProviders}
              >
                {loadingProviders ? (
                  <option value="">Loading providers...</option>
                ) : (
                  <>
                    {availableProviders.map(p => (
                      <option value={p.name}>{p.name}</option>
                    ))}
                    <option value="new" className="font-bold text-blue-600">+ new</option>
                  </>
                )}
              </select>
            </div>
            <div className="flex-1">
              <label for="model-name-input" className="block text-sm font-medium text-gray-700 mb-1">
                Model {loadingModels && <span className="text-gray-400 text-xs font-normal">(loading...)</span>}
              </label>
              <input
                id="model-name-input"
                type="text"
                list="model-options"
                className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                value={model}
                onChange={(e) => setModel(e.currentTarget.value)}
                placeholder="e.g. gpt-4o or gemini-1.5-pro"
              />
              <datalist id="model-options">
                {modelsCache[provider]?.map(m => (
                  <option key={m} value={m} />
                ))}
              </datalist>
            </div>
          </div>

          </div>

          <div className="shrink-0 flex justify-between items-center pt-2 border-t border-gray-200">
            <button
              type="button"
              onClick={handleTest}
              className="px-4 py-2 bg-gray-100 text-gray-700 border border-gray-300 rounded hover:bg-gray-200 disabled:opacity-50"
              disabled={loading || testing}
            >
              {testing ? "Testing..." : "Test Connection"}
            </button>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 hover:bg-gray-100 rounded"
                disabled={loading || testing}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 disabled:opacity-50"
                disabled={loading || testing}
              >
                {loading ? "Saving..." : (existingAgent ? "Save Agent" : "Create Agent")}
              </button>
            </div>
          </div>
        </form>
      </div>
      {providerModalMode !== null && (
        <ProviderModal
          existingProvider={providerModalMode === "edit" ? availableProviders.find(p => p.name === provider) : undefined}
          existingProviders={availableProviders.map(p => p.name)}
          onClose={() => setProviderModalMode(null)}
          onSuccess={async (newProviderName) => {
            try {
              const providers = await fetchProviders();
              setAvailableProviders(providers);
              setProvider(newProviderName);
            } catch (err) {
              console.error("Failed to reload providers", err);
            }
          }}
        />
      )}
    </div>
  );
}
