import { useState } from "preact/hooks";
import type { TargetedEvent } from "preact";
import { updateApiKey } from "../api";

interface ApiKeyModalProps {
  selectedApiKey: string;
  existingApiKeys: string[];
  onClose: () => void;
  onSuccess: (apiKeyName: string) => void;
}

export default function ApiKeyModal({ selectedApiKey, existingApiKeys, onClose, onSuccess }: ApiKeyModalProps) {
  const [keyName, setKeyName] = useState(selectedApiKey);
  const [keyValue, setKeyValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [actionSuccess, setActionSuccess] = useState<{ success: boolean, message: string } | null>(null);

  const isNameFixed = !!selectedApiKey;
  const isNameTaken = !selectedApiKey && existingApiKeys.includes(keyName.trim());

  const handleSubmit = async (e: TargetedEvent) => {
    e.preventDefault();
    if (!keyName.trim()){
      setActionSuccess({success: false, message: "Name cannot be empty"});
      return;
    }

    setLoading(true);
    setActionSuccess(null);

    try {
      await updateApiKey(keyName, keyValue);
      onSuccess(keyName);
      onClose();
    } catch (err: any) {
      setActionSuccess({success: false, message: err.message || "Failed to create provider"});
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-start justify-center z-60 p-4 overflow-y-auto">
      <div className="bg-white rounded-lg p-6 w-125 max-w-[90vw] shadow-xl max-h-[calc(100vh-2rem)] flex flex-col overflow-hidden">
        <div className="shrink-0">
          <h2 className="text-xl font-bold">{selectedApiKey ? 'Edit API Key' : 'Add New API Key'}</h2>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 flex flex-col overflow-hidden" autocomplete="off">
          <div className="flex-1 overflow-y-auto flex flex-col gap-4 pt-4 pr-1">
            {actionSuccess && (
              <div className={`p-3 border rounded text-sm ${
                actionSuccess.success
                  ? "bg-green-100 border-green-300 text-green-700" 
                  : "bg-red-100 border border-red-300 text-red-700"
              }`}>
                {actionSuccess.message}
              </div>
            )}

          <div className="flex gap-4">
            <div className="flex-1">
              <label for="api-key-name-input" className="block text-sm font-medium text-gray-700 mb-1">API Key Name</label>
              <input
                id="api-key-name-input"
                type="text"
                className={`w-full border rounded p-2 focus:ring-2 focus:outline-none ${
                isNameTaken 
                  ? "border-red-500 focus:ring-red-500 bg-red-50" 
                  : "focus:ring-blue-500"
              } ${isNameFixed ? "bg-gray-100 text-gray-500" : ""}`}
                value={keyName}
                onChange={(e) => setKeyName(e.currentTarget.value.toUpperCase())}
                required
                placeholder="e.g. OPENAI"
                disabled={isNameFixed}
              />
              {isNameTaken && (
                <p className="text-red-500 text-xs mt-1">This API key already exists.</p>
              )}
            </div>
            <div className="flex-1">
              <label for="api-key-value-input" className="block text-sm font-medium text-gray-700 mb-1">API Key Value</label>
              <input
                id="api-key-value-input"
                type="text"
                className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                value={keyValue}
                onChange={(e) => setKeyValue(e.currentTarget.value)}
                placeholder="e.g. my_secret_token"
              />
            </div>
          </div>

          </div>

          <div className="shrink-0 flex justify-end gap-3 pt-4 border-t">
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
              disabled={loading}
            >
              {loading ? "Saving..." : (isNameFixed ? "Save API Key" : "Add API Key")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
