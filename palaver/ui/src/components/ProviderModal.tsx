import { useState } from "preact/hooks";
import type { TargetedEvent } from "preact";
import { createProvider, updateProvider } from "../api";
import type { ProviderConfig } from "../api";

interface ProviderModalProps {
  existingProviders: string[];
  onClose: () => void;
  onSuccess: (newProvider: string) => void;
  existingProvider?: ProviderConfig;
}

export default function ProviderModal({ existingProviders, onClose, onSuccess, existingProvider }: ProviderModalProps) {
  const [service, setService] = useState(existingProvider?.service || "openai");
  const [apiBase, setApiBase] = useState(existingProvider?.api_base || "");
  const [apiKeyEnvVar, setApiKeyEnvVar] = useState(existingProvider?.api_key_env_var || "");
  const [name, setName] = useState(existingProvider?.name || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isNameTaken = !existingProvider && existingProviders.includes(name.trim());

  const handleSubmit = async (e: TargetedEvent) => {
    e.preventDefault();
    if (!name.trim() || !apiBase.trim()) {
      setError("Name and API Base URL are required");
      return;
    }

    if (isNameTaken) {
      setError("Provider name already exists");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const data: ProviderConfig = {
        service: service,
        api_base: apiBase.trim(),
        api_key_env_var: apiKeyEnvVar.trim(),
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
      setError(err.message || "Failed to create provider");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-60">
      <div className="bg-white rounded-lg p-6 w-125 max-w-[90vw] shadow-xl">
        <h2 className="text-xl font-bold mb-4">{existingProvider ? 'Edit Provider' : 'Create New Provider'}</h2>
        
        {error && (
          <div className="mb-4 p-3 bg-red-100 border border-red-300 text-red-700 rounded text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
            <input
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
            <label className="block text-sm font-medium text-gray-700 mb-1">API Base URL *</label>
            <input
              type="url"
              className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              value={apiBase}
              onChange={(e) => setApiBase(e.currentTarget.value)}
              placeholder="e.g. https://api.openai.com/v1"
              required
            />
          </div>

          <div className="flex gap-4">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">API Style</label>
              <select 
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
              <label className="block text-sm font-medium text-gray-700 mb-1">API Key Env Var</label>
              <input
                type="text"
                className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                value={apiKeyEnvVar}
                onChange={(e) => setApiKeyEnvVar(e.currentTarget.value)}
                placeholder="e.g. OPENAI_API_KEY"
              />
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
    </div>
  );
}
