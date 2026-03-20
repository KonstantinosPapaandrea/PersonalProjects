class AnnotationGraphLine extends Animatable {
    /**
     * @return {number}
     */
    get maxFrame() {
        return this._maxFrame;
    }

    /**
     * @param value {number | null}
     */
    set maxFrame(value) {
        this._maxFrame = value ?? this.getNumFrames();
        this._maxFrame = Math.max(this._maxFrame, this.getNumFrames())
    }

    /**
     * @param canvas {HTMLCanvasElement}
     * @param motionObj {{}}
     * @param featureKey {string | null}
     * @param strokeStyle {string}
     * @param lineWidth {number}
     * @param maxFrame {number | null}
     */
    constructor(
        canvas,
        motionObj,
        featureKey = null,
        strokeStyle= "#4CAF50",
        lineWidth = 2,
        maxFrame = null
    ) {
        super();
        this.canvas = canvas;
        this.ctx = this.canvas.getContext("2d");
        this.strokeStyle = strokeStyle;
        this.lineWidth = lineWidth;
        this.motionData = motionObj;
        this.featureKey = featureKey?? Object.keys(this.motionData)[0];
        this.maxFrame = maxFrame??  this.getNumFrames();
        this._frame = 0
        this._maxFrame = maxFrame;
    }

    /**
     * @param featureKey {string}
     */
    setFeatureKey(featureKey) {
        this.featureKey = featureKey;
    }

    drawGraph() {
        const width = this.canvas.width;
        const height = this.canvas.height;

        const min = 0;
        const max = 1;
        const range = max - min;
        const ctx = this.ctx

        ctx.beginPath();
        ctx.strokeStyle = this.strokeStyle
        ctx.lineWidth = this.lineWidth

         this.getData().forEach((value, index) => {
            const denom = Math.max(this.getNumFrames() - 1, 1);
            const x = (index / denom) * width;
            const y = height - ((value - min) / range) * height;

            if (index === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });

        // Add y-axis labels
        ctx.font = '30px Arial';
        ctx.fillStyle = 'black';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';

        // Label for maximum value (1)
        ctx.fillText('1', 14, 10);

        // Label for minimum value (0)
        ctx.fillText('0', 14, height - 10);

        ctx.stroke();
    }

    /**
     * @returns {number[]}
     */
    getData() {
        return this.motionData[this.featureKey]
    }

    getNumFrames() {
        return this.getData()?.length?? 0
    }

    gotoFrame(frame) {
        super.gotoFrame(frame)

        this.updateGraphMarker()
    }

    updateGraphMarker() {
        if (!this.featureKey || !this.motionData || !this.motionData[this.featureKey]){
            return;
        }
        const x = (this.frame / (this.maxFrame - 1)) * this.canvas.width;
        const ctx = this.ctx;
        const canvasHeight = this.canvas.height;

        const min = 0;
        const max = 1;
        const value = this.motionData[this.featureKey][this.frame];
        if (!value)
            return;

        const range = max - min;

        // ctx.clearRect(0, 0, this.graphCanvas.width, this.graphCanvas.height);
        //
        // this.drawGraph();

        ctx.beginPath();
        // Add y-axis labels
        ctx.font = '36px Arial';
        ctx.fillStyle = 'white';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';

        const y = canvasHeight - ((value - min) / range) * canvasHeight;
        let letterHeight = y  - 15;
        if ( y > canvasHeight ) {
            letterHeight = y  + 25;
        }
        else if ( y <= 0 ) {
            letterHeight = y - 25;
        }
        // Label for maximum value (1)
        ctx.fillText(value.toPrecision(2), x, letterHeight);
        ctx.stroke();

        ctx.beginPath();
        ctx.strokeStyle = 'red';
        ctx.lineWidth = 2;
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvasHeight);
        ctx.stroke();
    }

    reset() {}

}
