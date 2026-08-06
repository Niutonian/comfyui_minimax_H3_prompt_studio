import { app } from "../../../scripts/app.js";

const NODE_NAME = "MiniMaxH3TextPreview";
const MIN_WIDTH = 320;
const MIN_HEIGHT = 180;

function payloadToText(payload) {
    if (payload == null) return "";
    if (Array.isArray(payload)) {
        return payload.flat(Infinity).map((value) => String(value ?? "")).join("\n");
    }
    return String(payload);
}

app.registerExtension({
    name: "MiniMaxH3PromptStudio.TextPreview",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;

        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = originalCreated?.apply(this, arguments);

            const textArea = document.createElement("textarea");
            textArea.readOnly = true;
            textArea.placeholder = "Generated text will appear here after execution.";
            textArea.spellcheck = false;
            textArea.style.cssText = `
                width: 100%;
                height: 100%;
                box-sizing: border-box;
                resize: none;
                overflow: auto;
                padding: 8px;
                border: 1px solid #555;
                border-radius: 4px;
                background: #181818;
                color: #e6e6e6;
                font: 12px/1.4 monospace;
                white-space: pre-wrap;
            `;

            const widget = this.addDOMWidget(
                "preview",
                "minimax_h3_text_preview",
                textArea,
                {
                    getValue: () => textArea.value,
                    setValue: (value) => {
                        textArea.value = payloadToText(value);
                    },
                    serialize: true,
                    getMinHeight: () => 120,
                },
            );

            this._minimaxH3PreviewElement = textArea;
            this._minimaxH3PreviewWidget = widget;
            this.setSize?.([
                Math.max(this.size?.[0] ?? 0, MIN_WIDTH),
                Math.max(this.size?.[1] ?? 0, MIN_HEIGHT),
            ]);
            return result;
        };

        const originalExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            originalExecuted?.apply(this, arguments);
            const text = payloadToText(message?.text);
            if (this._minimaxH3PreviewElement) this._minimaxH3PreviewElement.value = text;
            if (this._minimaxH3PreviewWidget) this._minimaxH3PreviewWidget.value = text;
            app.graph.setDirtyCanvas(true, false);
        };

        const originalResize = nodeType.prototype.onResize;
        nodeType.prototype.onResize = function (size) {
            originalResize?.apply(this, arguments);
            this.size[0] = Math.max(this.size[0], MIN_WIDTH);
            this.size[1] = Math.max(this.size[1], MIN_HEIGHT);
        };
    },
});
