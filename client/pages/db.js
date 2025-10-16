(async function() {
    const dbContent = document.getElementById('db-content');

    try {
        const response = await fetch('/api/db');
        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        let html = '';
        for (const tableName in data) {
            html += `<h3 class="text-lg font-semibold text-gray-200 mt-6 mb-2">${tableName}</h3>`;
            const tableData = data[tableName];

            if (tableData.length === 0) {
                html += '<p class="text-gray-400">No data in this table.</p>';
                continue;
            }

            html += `<div class="overflow-x-auto"><table class="min-w-full divide-y divide-gray-700">`;
            // Headers
            html += `<thead class="bg-gray-700/50"><tr>`;
            for (const header of tableData[0]) {
                html += `<th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">${header}</th>`;
            }
            html += `</tr></thead>`;

            // Body
            html += `<tbody class="bg-gray-800 divide-y divide-gray-700">`;
            for (let i = 1; i < tableData.length; i++) {
                html += `<tr>`;
                for (const cell of tableData[i]) {
                    html += `<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-300">${cell}</td>`;
                }
                html += `</tr>`;
            }
            html += `</tbody></table></div>`;
        }
        dbContent.innerHTML = html;
    } catch (error) {
        dbContent.innerHTML = `<p class="text-red-400">Error loading database content: ${error.message}</p>`;
    }
})();
