class AnnotationBar extends Animatable {
    /**
     * @param motionData {Object.<string, number[]>}
     * @param featureBar {FeatureBar}
     * @param valueDisplay {ValueDisplay}
     * @param featureKey {string | null}
     * @param color {string}
     */
    constructor(
        motionData,
        featureBar,
        valueDisplay,
        featureKey = null,
        color = "#4fff00"
    ) {
        super();
        this.color = color;
        this.featureBar = featureBar;
        this.valueDisplay = valueDisplay;
        this.motionData = motionData;
        this._frame = 0;
        this._featureKey = featureKey?? "BODY";
    }
  set targetFrames(n) { this._targetFrames = n; }
    get targetFrames()   { return this._targetFrames ?? null; }
    get frame() {
        return this._frame;
    }

    /**
     * @returns {string}
     */
    get featureKey() {
        return this._featureKey;
    }

    /**
     * @param value {string}
     */
    set featureKey(value) {
        this._featureKey = value;
    }

    get data() {
        return this.getData()
    }

    getData() {
        return this.motionData[this.featureKey]
    }
      getNumFrames() {
        // If the player gave us a BVH-length hint, use it
        return this._targetFrames ?? this.data.length;
    }

    gotoFrame(frame) {
        super.gotoFrame(frame)

        this.updateFeatureBar()
    }

 updateFeatureBar() {
    // No feature selected or no data yet? Gracefully clear UI.
    if (!this.featureKey) return;

    const series = this.data; // current feature's array (set by the class or by your code)
    if (!Array.isArray(series) || series.length === 0) {
        if (this.featureBar?.isValid)   this.featureBar.value = 0;
        if (this.valueDisplay?.isValid) this.valueDisplay.text = "0.00";
        return;
    }

    // Map BVH playhead frame → annotation sample index with clamping
    const totalFrames = Math.max(this.getNumFrames() - 1, 1); // BVH timeline length - 1
    const srcFrames   = Math.max(series.length    - 1, 0);    // annotation length - 1
    const idxRaw      = Math.floor((this.frame / totalFrames) * srcFrames);
    const idx         = Math.min(Math.max(idxRaw, 0), series.length - 1);

    // Coerce to a safe number
    const raw   = series[idx];
    const value = Number.isFinite(raw) ? raw : 0;

    const height = value * 100;
    if (this.featureBar?.isValid)   this.featureBar.value = height;
    if (this.valueDisplay?.isValid) this.valueDisplay.text = value.toFixed(2);
}

    reset() {
        this.gotoFrame(this.frame)
    }

}
