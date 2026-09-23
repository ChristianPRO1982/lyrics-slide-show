(() => {
    const DEFAULT_OPTIONS = {
        items: [],
        action: "auto",
        target: null,
        targetId: "",
        size: 220,
        fontSize: 22,
        fontColor: "",
        backgroundColor: "transparent",
        backgroundAlpha: 0,
        autoRotateSpeed: 0.003,
        edgeRotateSpeed: 0.014,
        centerDeadZone: 0.28,
        minScale: 0.58,
        maxScale: 1.12,
        backOpacity: 0.16,
        frontOpacity: 1,
    };

    const STYLE_ID = "lss-word-sphere-styles";
    const INSTANCE_KEY = "__lssWordSphereInstance";
    const reduceMotion = window.matchMedia
        ? window.matchMedia("(prefers-reduced-motion: reduce)")
        : null;

    const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

    const toNumber = (value, fallback) => {
        const number = Number(value);
        return Number.isFinite(number) ? number : fallback;
    };

    const injectStyles = () => {
        if (document.getElementById(STYLE_ID)) {
            return;
        }

        const style = document.createElement("style");
        style.id = STYLE_ID;
        style.textContent = `
.lss-word-sphere {
    position: relative;
    width: var(--lss-word-sphere-size, 220px);
    height: var(--lss-word-sphere-size, 220px);
    max-width: 100%;
    overflow: hidden;
    border-radius: 50%;
    background: var(--lss-word-sphere-background, transparent);
    touch-action: none;
    user-select: none;
}

.lss-word-sphere__item {
    position: absolute;
    left: 50%;
    top: 50%;
    padding: 0.12em 0.22em;
    border: 0;
    background: transparent;
    color: var(--lss-word-sphere-color, currentColor);
    font: inherit;
    font-size: var(--lss-word-sphere-font-size, 22px);
    line-height: 1;
    text-decoration: none;
    white-space: nowrap;
    cursor: pointer;
    transform-origin: 50% 50%;
    will-change: transform, opacity, color;
}

.lss-word-sphere__item:hover,
.lss-word-sphere__item:focus-visible {
    outline: 2px solid currentColor;
    outline-offset: 2px;
}

.lss-word-sphere__item.is-back {
    pointer-events: none;
}
`;
        document.head.appendChild(style);
    };

    const parseColor = (value, alpha) => {
        const color = String(value || "").trim();
        if (!color || color === "transparent") {
            return "transparent";
        }
        const nextAlpha = clamp(toNumber(alpha, 1), 0, 1);
        if (color.startsWith("#") && (color.length === 4 || color.length === 7)) {
            const hex = color.length === 4
                ? `#${color[1]}${color[1]}${color[2]}${color[2]}${color[3]}${color[3]}`
                : color;
            const red = parseInt(hex.slice(1, 3), 16);
            const green = parseInt(hex.slice(3, 5), 16);
            const blue = parseInt(hex.slice(5, 7), 16);
            return `rgba(${red}, ${green}, ${blue}, ${nextAlpha})`;
        }
        if (nextAlpha < 1) {
            return `color-mix(in srgb, ${color} ${Math.round(nextAlpha * 100)}%, transparent)`;
        }
        return color;
    };

    const normalizeItem = (item) => {
        if (typeof item === "string") {
            return {
                label: item,
                value: item,
                url: "",
                action: "",
            };
        }

        const label = String(item?.label ?? item?.value ?? "");
        return {
            label,
            value: String(item?.value ?? label),
            url: String(item?.url ?? ""),
            action: String(item?.action ?? ""),
        };
    };

    const resolveAction = (item, fallbackAction) => {
        const action = item.action || fallbackAction || "auto";
        if (action === "auto") {
            return item.url ? "link" : "insert";
        }
        return action;
    };

    const fibonacciPoint = (index, count) => {
        const offset = 2 / count;
        const increment = Math.PI * (3 - Math.sqrt(5));
        const y = (index * offset) - 1 + (offset / 2);
        const radius = Math.sqrt(1 - y * y);
        const phi = index * increment;

        return {
            x: Math.cos(phi) * radius,
            y,
            z: Math.sin(phi) * radius,
        };
    };

    const rotatePoint = (point, angleX, angleY) => {
        const cosX = Math.cos(angleX);
        const sinX = Math.sin(angleX);
        const cosY = Math.cos(angleY);
        const sinY = Math.sin(angleY);

        const y1 = point.y * cosX - point.z * sinX;
        const z1 = point.y * sinX + point.z * cosX;
        const x2 = point.x * cosY + z1 * sinY;
        const z2 = -point.x * sinY + z1 * cosY;

        return {
            x: x2,
            y: y1,
            z: z2,
        };
    };

    const insertIntoTarget = (target, value) => {
        if (!(target instanceof HTMLTextAreaElement) && !(target instanceof HTMLInputElement)) {
            return;
        }

        const start = target.selectionStart ?? target.value.length;
        const end = target.selectionEnd ?? target.value.length;
        target.value = `${target.value.slice(0, start)}${value}${target.value.slice(end)}`;
        const nextPosition = start + value.length;
        target.focus();
        target.setSelectionRange(nextPosition, nextPosition);
        target.dispatchEvent(new Event("input", { bubbles: true }));
    };

    class WordSphere {
        constructor(container, options = {}) {
            if (!(container instanceof HTMLElement)) {
                throw new TypeError("LSSWordSphere.create expects an HTMLElement container.");
            }

            injectStyles();

            if (container[INSTANCE_KEY]) {
                container[INSTANCE_KEY].destroy();
            }

            this.container = container;
            this.options = { ...DEFAULT_OPTIONS, ...options };
            this.items = [];
            this.nodes = [];
            this.angleX = 0;
            this.angleY = 0;
            this.pointerX = 0;
            this.pointerY = 0;
            this.pointerInside = false;
            this.dragging = false;
            this.dragMoved = false;
            this.suppressNextClick = false;
            this.skipNextClick = false;
            this.lastPointer = null;
            this.paused = false;
            this.destroyed = false;
            this.frameId = null;

            this.onPointerMove = this.onPointerMove.bind(this);
            this.onPointerLeave = this.onPointerLeave.bind(this);
            this.onPointerDown = this.onPointerDown.bind(this);
            this.onPointerUp = this.onPointerUp.bind(this);
            this.tick = this.tick.bind(this);

            this.prepareContainer();
            this.setItems(this.options.items);
            this.bind();
            this.resume();

            container[INSTANCE_KEY] = this;
        }

        prepareContainer() {
            const size = Math.max(80, toNumber(this.options.size, DEFAULT_OPTIONS.size));
            const fontSize = Math.max(8, toNumber(this.options.fontSize, DEFAULT_OPTIONS.fontSize));
            const background = parseColor(this.options.backgroundColor, this.options.backgroundAlpha);

            this.container.classList.add("lss-word-sphere");
            this.container.style.setProperty("--lss-word-sphere-size", `${size}px`);
            this.container.style.setProperty("--lss-word-sphere-font-size", `${fontSize}px`);
            this.container.style.setProperty("--lss-word-sphere-background", background);
            if (this.options.fontColor) {
                this.container.style.setProperty("--lss-word-sphere-color", this.options.fontColor);
            }
        }

        bind() {
            this.container.addEventListener("pointermove", this.onPointerMove);
            this.container.addEventListener("pointerleave", this.onPointerLeave);
            this.container.addEventListener("pointerdown", this.onPointerDown);
            window.addEventListener("pointerup", this.onPointerUp);
            window.addEventListener("pointercancel", this.onPointerUp);
        }

        unbind() {
            this.container.removeEventListener("pointermove", this.onPointerMove);
            this.container.removeEventListener("pointerleave", this.onPointerLeave);
            this.container.removeEventListener("pointerdown", this.onPointerDown);
            window.removeEventListener("pointerup", this.onPointerUp);
            window.removeEventListener("pointercancel", this.onPointerUp);
        }

        setItems(items) {
            this.items = Array.isArray(items) ? items.map(normalizeItem).filter((item) => item.label) : [];
            this.nodes.forEach(({ element }) => element.remove());
            this.nodes = [];

            const count = Math.max(this.items.length, 1);
            this.items.forEach((item, index) => {
                const action = resolveAction(item, this.options.action);
                const node = action === "link" && item.url
                    ? document.createElement("a")
                    : document.createElement("button");

                node.className = "lss-word-sphere__item";
                node.textContent = item.label;
                node.dataset.lssWordSphereValue = item.value;

                const activateItem = (event, fromPointer) => {
                    if (this.suppressNextClick || this.skipNextClick) {
                        event.preventDefault();
                        event.stopPropagation();
                        this.suppressNextClick = false;
                        this.skipNextClick = false;
                        return;
                    }
                    if (action === "insert") {
                        insertIntoTarget(this.resolveTarget(), item.value);
                        this.skipNextClick = fromPointer;
                        if (fromPointer) {
                            window.setTimeout(() => {
                                this.skipNextClick = false;
                            }, 250);
                        }
                    }
                };

                node.addEventListener("click", (event) => {
                    activateItem(event, false);
                });

                node.addEventListener("pointerup", (event) => {
                    if (action === "insert") {
                        activateItem(event, true);
                    }
                });

                if (node instanceof HTMLAnchorElement) {
                    node.href = item.url;
                } else {
                    node.type = "button";
                }

                this.nodes.push({
                    element: node,
                    basePoint: fibonacciPoint(index, count),
                });
                this.container.appendChild(node);
            });

            this.render();
        }

        resolveTarget() {
            if (typeof this.options.targetId === "string" && this.options.targetId) {
                const targetById = document.getElementById(this.options.targetId);
                if (targetById instanceof HTMLTextAreaElement || targetById instanceof HTMLInputElement) {
                    return targetById;
                }
            }

            const target = this.options.target;
            if (target instanceof HTMLTextAreaElement || target instanceof HTMLInputElement) {
                return target;
            }
            if (typeof target === "string" && target) {
                const targetBySelector = document.querySelector(target);
                if (targetBySelector instanceof HTMLTextAreaElement || targetBySelector instanceof HTMLInputElement) {
                    return targetBySelector;
                }
            }
            return null;
        }

        onPointerMove(event) {
            const rect = this.container.getBoundingClientRect();
            if (!rect.width || !rect.height) {
                return;
            }

            const x = ((event.clientX - rect.left) / rect.width - 0.5) * 2;
            const y = ((event.clientY - rect.top) / rect.height - 0.5) * 2;
            this.pointerX = clamp(x, -1, 1);
            this.pointerY = clamp(y, -1, 1);
            this.pointerInside = true;

            if (this.dragging && this.lastPointer) {
                const dx = event.clientX - this.lastPointer.x;
                const dy = event.clientY - this.lastPointer.y;
                if (Math.abs(dx) + Math.abs(dy) > 6) {
                    this.dragMoved = true;
                }
                this.angleY += dx * 0.006;
                this.angleX -= dy * 0.006;
                this.lastPointer = { x: event.clientX, y: event.clientY };
                this.render();
            }
        }

        onPointerLeave() {
            if (!this.dragging) {
                this.pointerX = 0;
                this.pointerY = 0;
                this.pointerInside = false;
            }
        }

        onPointerDown(event) {
            if (event.target instanceof Element && event.target.closest(".lss-word-sphere__item")) {
                return;
            }

            this.dragging = true;
            this.dragMoved = false;
            this.lastPointer = { x: event.clientX, y: event.clientY };
            this.container.setPointerCapture?.(event.pointerId);
        }

        onPointerUp() {
            this.suppressNextClick = this.dragMoved;
            this.dragging = false;
            this.dragMoved = false;
            this.lastPointer = null;
        }

        computeVelocity() {
            const deadZone = clamp(toNumber(this.options.centerDeadZone, DEFAULT_OPTIONS.centerDeadZone), 0, 0.95);
            const distance = Math.sqrt((this.pointerX ** 2) + (this.pointerY ** 2));
            const reduced = reduceMotion && reduceMotion.matches;
            const autoSpeed = reduced ? 0 : toNumber(this.options.autoRotateSpeed, DEFAULT_OPTIONS.autoRotateSpeed);
            const edgeSpeed = reduced ? 0.002 : toNumber(this.options.edgeRotateSpeed, DEFAULT_OPTIONS.edgeRotateSpeed);

            if (this.pointerInside && distance <= deadZone) {
                return {
                    x: 0,
                    y: 0,
                };
            }

            if (!this.pointerInside) {
                return {
                    x: 0,
                    y: autoSpeed,
                };
            }

            const force = clamp((distance - deadZone) / (1 - deadZone), 0, 1);
            return {
                x: -this.pointerY * edgeSpeed * force,
                y: this.pointerX * edgeSpeed * force,
            };
        }

        tick() {
            if (this.destroyed || this.paused) {
                return;
            }

            const velocity = this.computeVelocity();
            this.angleX += velocity.x;
            this.angleY += velocity.y;
            this.render();
            this.frameId = window.requestAnimationFrame(this.tick);
        }

        render() {
            const rect = this.container.getBoundingClientRect();
            const size = Math.min(rect.width || this.options.size, rect.height || this.options.size);
            const radius = size * 0.34;
            const minScale = toNumber(this.options.minScale, DEFAULT_OPTIONS.minScale);
            const maxScale = toNumber(this.options.maxScale, DEFAULT_OPTIONS.maxScale);
            const backOpacity = clamp(toNumber(this.options.backOpacity, DEFAULT_OPTIONS.backOpacity), 0, 1);
            const frontOpacity = clamp(toNumber(this.options.frontOpacity, DEFAULT_OPTIONS.frontOpacity), 0, 1);

            this.nodes.forEach(({ element, basePoint }) => {
                const point = rotatePoint(basePoint, this.angleX, this.angleY);
                const depth = (point.z + 1) / 2;
                const scale = minScale + ((maxScale - minScale) * depth);
                const opacity = backOpacity + ((frontOpacity - backOpacity) * depth);
                const x = point.x * radius;
                const y = point.y * radius;
                const isBack = point.z < -0.08;

                element.style.transform = `translate3d(calc(-50% + ${x}px), calc(-50% + ${y}px), 0) scale(${scale})`;
                element.style.opacity = String(opacity);
                element.style.zIndex = String(Math.round(depth * 1000));
                element.classList.toggle("is-back", isBack);
                element.setAttribute("aria-hidden", isBack ? "true" : "false");
                element.tabIndex = isBack ? -1 : 0;
            });
        }

        pause() {
            this.paused = true;
            if (this.frameId !== null) {
                window.cancelAnimationFrame(this.frameId);
                this.frameId = null;
            }
        }

        resume() {
            if (this.destroyed) {
                return;
            }
            this.paused = false;
            if (this.frameId === null) {
                this.frameId = window.requestAnimationFrame(this.tick);
            }
        }

        destroy() {
            this.pause();
            this.unbind();
            this.nodes.forEach(({ element }) => element.remove());
            this.nodes = [];
            this.container.classList.remove("lss-word-sphere");
            delete this.container[INSTANCE_KEY];
            this.destroyed = true;
        }
    }

    const readDatasetOptions = (container) => {
        const options = {};
        const dataset = container.dataset;

        if (dataset.lssWordSphereTarget) {
            options.target = dataset.lssWordSphereTarget;
        }
        if (dataset.lssWordSphereTargetId) {
            options.targetId = dataset.lssWordSphereTargetId;
        }
        if (dataset.lssWordSphereAction) {
            options.action = dataset.lssWordSphereAction;
        }
        [
            "size",
            "fontSize",
            "backgroundAlpha",
            "autoRotateSpeed",
            "edgeRotateSpeed",
            "centerDeadZone",
            "minScale",
            "maxScale",
            "backOpacity",
            "frontOpacity",
        ].forEach((key) => {
            const dataKey = `lssWordSphere${key[0].toUpperCase()}${key.slice(1)}`;
            if (dataset[dataKey] !== undefined) {
                options[key] = toNumber(dataset[dataKey], DEFAULT_OPTIONS[key]);
            }
        });
        if (dataset.lssWordSphereFontColor) {
            options.fontColor = dataset.lssWordSphereFontColor;
        }
        if (dataset.lssWordSphereBackgroundColor) {
            options.backgroundColor = dataset.lssWordSphereBackgroundColor;
        }

        return options;
    };

    const readConfig = (container) => {
        const options = readDatasetOptions(container);
        if (!container.id) {
            return options;
        }

        const configNode = Array.from(
            document.querySelectorAll('script[type="application/json"][data-lss-word-sphere-config-for]')
        ).find((node) => node.getAttribute("data-lss-word-sphere-config-for") === container.id);
        if (!configNode) {
            return options;
        }

        try {
            return {
                ...options,
                ...JSON.parse(configNode.textContent || "{}"),
            };
        } catch (error) {
            window.console.error("Invalid LSSWordSphere config.", error);
            return options;
        }
    };

    const create = (container, options = {}) => new WordSphere(container, options);

    const initAll = (root = document) => {
        const scope = root && typeof root.querySelectorAll === "function" ? root : document;
        const containers = Array.from(scope.querySelectorAll("[data-lss-word-sphere]"));
        if (scope instanceof HTMLElement && scope.matches("[data-lss-word-sphere]")) {
            containers.unshift(scope);
        }
        return containers.map((container) => create(container, readConfig(container)));
    };

    window.LSSWordSphere = {
        create,
        initAll,
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => initAll());
    } else {
        initAll();
    }
})();
