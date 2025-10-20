(async function() {
    // A short delay to ensure the page elements are in the DOM
    await new Promise(resolve => setTimeout(resolve, 0));

    const errorDiv = document.getElementById('db-error-message');
    const controlsDiv = document.getElementById('lineup-controls');

    async function init() {
        try {
            const response = await fetch('/api/lineups_page_data');
            const data = await response.json();

            if (!response.ok || !data.db_exists) {
                throw new Error(data.error || 'Database has not been initialized.');
            }

            // If DB exists, show controls and hide error message
            controlsDiv.classList.remove('hidden');
            errorDiv.classList.add('hidden');

            // Future initialization logic for dropdowns, etc., will go here

        } catch (error) {
            console.error('Initialization error:', error);
            // If there's an error (e.g., DB not found), show the error message
            // and ensure the main controls are hidden.
            errorDiv.classList.remove('hidden');
            controlsDiv.classList.add('hidden');
        }
    }

    init();
})();
