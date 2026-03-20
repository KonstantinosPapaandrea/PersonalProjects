class ProgressBar extends Animatable {
    /**
     * @param progressBarId {string}
     * @param playPauseButtonId {string}
     */
    constructor(progressBarId, playPauseButtonId) {
        super()
        this.progressBar = document.getElementById(progressBarId);
        this.playPauseButton = document.getElementById(playPauseButtonId);
        this.playPauseIcon = this.playPauseButton.querySelector("i");
        this.numFrames = 0;
        this.playing = false;

        this.onUpdateCallback = null;
        this.onTogglePlayCallback = null;

        this.progressBar.addEventListener('input', this.onInput.bind(this));
        this.playPauseButton.addEventListener('click', this.togglePlay.bind(this));
    }

    enable() {
        this.progressBar.disabled = false;
        this.playPauseButton.disabled = false;

        document.addEventListener('keydown', (event) => {
            if (event.code === 'Space') {
                event.preventDefault(); // Prevent the default space bar action (scrolling)
                this.playPauseButton.click(); // Trigger the specific button's click event
            }
        });
    }

    onInput() {
        if (this.onUpdateCallback) {
            this.onUpdateCallback(Math.floor(this.progressBar.value * this.numFrames / 100));
        }
    }

    /**
     * @param numFrames {number}
     */
    setNumFrames(numFrames) {
        this.numFrames = numFrames;
    }

    /**
     * @param callback {(number) => {}}
     */
    setUpdateCallback(callback) {
        this.onUpdateCallback = callback;
    }

    /**
     * @param callback {() => {}}
     */
    setTogglePlayCallback(callback) {
        this.onTogglePlayCallback = callback;
    }

    togglePlay() {
        if (this.onTogglePlayCallback) {
            this.onTogglePlayCallback();
        }
        this.playPauseIcon.className = this.playing
            ? "fas fa-pause"
            : "fas fa-play";
    }

    getNumFrames() {
        return this.numFrames;
    }

    gotoFrame(frame) {

        super.gotoFrame(frame)

        this.progressBar.value = (this.frame / this.numFrames) * 100;
    }
}