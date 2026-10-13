import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

const NODE_NAME = "MiniMaxH3LLMProvider";

app.registerExtension({
    name: "MiniMaxH3PromptStudio.ModelPicker",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;

        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = originalCreated?.apply(this, arguments);
            const providerWidget = this.widgets?.find((w) => w.name === "provider");
            const originalModelWidget = this.widgets?.find((w) => w.name === "model");
            const baseUrlWidget = this.widgets?.find((w) => w.name === "base_url");
            if (!providerWidget || !originalModelWidget || !baseUrlWidget) return result;

            // A STRING widget remains a text control even if its type property is
            // changed later. Replace it with a real combo at the same widget index,
            // retaining the backend input name and serialized workflow position.
            const modelIndex = this.widgets.indexOf(originalModelWidget);
            const initialModel = originalModelWidget.value || "Loading models…";
            this.widgets.splice(modelIndex, 1);
            originalModelWidget.onRemove?.();
            const modelWidget = this.addWidget(
                "combo",
                "model",
                initialModel,
                () => {},
                { values: [initialModel] },
            );
            this.widgets.splice(this.widgets.indexOf(modelWidget), 1);
            this.widgets.splice(modelIndex, 0, modelWidget);

            let discoverySequence = 0;
            let pendingRequest;
            const refreshModels = async (selectFirst = false) => {
                const sequence = ++discoverySequence;
                pendingRequest?.abort();
                pendingRequest = new AbortController();
                const previousModel = modelWidget.value;
                this.setDirtyCanvas?.(true, true);
                try {
                    const query = new URLSearchParams({
                        provider: providerWidget.value,
                        base_url: baseUrlWidget.value || "",
                    });
                    const response = await api.fetchApi(
                        `/minimax_h3_prompt_studio/models?${query.toString()}`,
                        { cache: "no-store", signal: pendingRequest.signal },
                    );
                    const data = await response.json();
                    if (sequence !== discoverySequence) return;
                    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
                    const models = data.models || [];
                    const choices = [...models];
                    if (!selectFirst && previousModel && !choices.includes(previousModel)) {
                        choices.unshift(previousModel);
                    }
                    modelWidget.options.values = choices.length ? choices : ["No models found"];
                    const selected = selectFirst
                        ? models[0]
                        : (choices.includes(previousModel) ? previousModel : choices[0]);
                    modelWidget.value = selected || "No models found";
                    modelWidget.callback?.(modelWidget.value);
                } catch (error) {
                    if (sequence !== discoverySequence || error.name === "AbortError") return;
                    const message = `⚠ Discovery failed: ${error.message || error}`;
                    modelWidget.options.values = previousModel
                        ? [previousModel, message]
                        : [message];
                    modelWidget.value = previousModel || message;
                }
                this.setSize?.(this.computeSize());
                this.setDirtyCanvas?.(true, true);
            };

            this.addWidget("button", "refresh model list", null, () => refreshModels(false));
            this.addWidget("button", "enter model manually", null, () => {
                const value = window.prompt("Model identifier", modelWidget.value || "");
                if (!value?.trim()) return;
                ++discoverySequence;
                pendingRequest?.abort();
                const model = value.trim();
                modelWidget.options.values = [model, ...modelWidget.options.values.filter((item) => item !== model)];
                modelWidget.value = model;
                modelWidget.callback?.(model);
                this.setDirtyCanvas?.(true, true);
            });

            const originalProviderCallback = providerWidget.callback;
            providerWidget.callback = (value) => {
                originalProviderCallback?.call(providerWidget, value);
                refreshModels(true);
            };

            const originalBaseUrlCallback = baseUrlWidget.callback;
            baseUrlWidget.callback = (value) => {
                originalBaseUrlCallback?.call(baseUrlWidget, value);
                refreshModels(false);
            };

            setTimeout(() => refreshModels(false), 0);
            return result;
        };
    },
});
