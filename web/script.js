document.addEventListener('DOMContentLoaded', () => {
    const queryInput = document.getElementById('query-input');
    const searchBtn = document.getElementById('search-btn');
    const statusIndicator = document.getElementById('status-indicator');
    const resultsArea = document.getElementById('results-area');
    const resultsContent = document.getElementById('results-content');
    const statusText = document.getElementById('status-text');
    const resultCount = document.getElementById('result-count');
    const suggestionChips = document.querySelectorAll('.suggestion-chip');

    // Steps
    const stepPlan = document.getElementById('step-plan');
    const stepExec = document.getElementById('step-exec');
    const stepVerify = document.getElementById('step-verify');

    function setStep(step) {
        stepPlan.classList.remove('active');
        stepExec.classList.remove('active');
        stepVerify.classList.remove('active');

        if (step >= 1) stepPlan.classList.add('active');
        if (step >= 2) stepExec.classList.add('active');
        if (step >= 3) stepVerify.classList.add('active');
    }

    async function performSearch(query) {
        if (!query.trim()) return;

        // Reset UI
        resultsArea.classList.add('hidden');
        statusIndicator.classList.remove('hidden');
        statusText.textContent = "Initializing agent...";
        setStep(0);

        try {
            // Simulate steps for better UX (since we might not get real-time stream in this simple fetch)
            // In a real streaming setup, we'd update this based on events.
            // For now, we'll just show a generic loading state that updates periodically
            let step = 1;
            setStep(1);
            statusText.textContent = "Planning search strategy...";

            const interval = setInterval(() => {
                step++;
                if (step > 3) step = 1;
                setStep(step);
                if (step === 1) statusText.textContent = "Refining plan...";
                if (step === 2) statusText.textContent = "Executing searches across APIs...";
                if (step === 3) statusText.textContent = "Verifying results quality...";
            }, 2000);

            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: query }),
            });

            clearInterval(interval);

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
            
            // Render Markdown
            resultsContent.innerHTML = marked.parse(data.response);
            
            // Update result count (simple heuristic or just show "Done")
            resultCount.textContent = "Search Complete";
            
            statusIndicator.classList.add('hidden');
            resultsArea.classList.remove('hidden');

        } catch (error) {
            console.error('Error:', error);
            statusText.textContent = "An error occurred. Please try again.";
            clearInterval(interval); // Ensure interval is cleared on error
        }
    }

    searchBtn.addEventListener('click', () => {
        performSearch(queryInput.value);
    });

    queryInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            performSearch(queryInput.value);
        }
    });

    suggestionChips.forEach(chip => {
        chip.addEventListener('click', () => {
            queryInput.value = chip.textContent;
            performSearch(chip.textContent);
        });
    });
});
