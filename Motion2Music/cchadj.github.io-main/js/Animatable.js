class Animatable {
    /**
     * @param frame
     */
    constructor(frame = 0) {
        this._frame = frame
    }
    /**
     * @returns {number}
     */
    getNumFrames() {
        throw new Error("Method 'getNumFrame()' must be implemented.");
    }

    /**
     * @param frame {number}
     * @returns {void}
     */
    gotoFrame(frame) {
        if (frame >= this.getNumFrames()) {
            frame = this.getNumFrames() - 1;
        }
        else if (frame < 0) {
            frame = 0;
        }
        this._frame = frame;
    }

    /**
     * should return current frame
     * @returns {number}
     */
    get frame() { return  this._frame; }

    /**
     * @param deltaTime {number}
     */
    update(deltaTime) {}

    reset() {}
}