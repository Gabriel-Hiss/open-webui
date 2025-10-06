<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { getContext, onMount, tick } from 'svelte';
	import { fly } from 'svelte/transition';
	import { flyAndScale } from '$lib/utils/transitions';

	import { config, user, tools as _tools, mobile, settings, toolServers, models } from '$lib/stores';

	import { getOAuthClientAuthorizationUrl } from '$lib/apis/configs';
	import { getTools } from '$lib/apis/tools';

	import Knobs from '$lib/components/icons/Knobs.svelte';
	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Wrench from '$lib/components/icons/Wrench.svelte';
	import Sparkles from '$lib/components/icons/Sparkles.svelte';
	import Brain from '$lib/components/icons/Brain.svelte';
	import GlobeAlt from '$lib/components/icons/GlobeAlt.svelte';
	import Photo from '$lib/components/icons/Photo.svelte';
	import Terminal from '$lib/components/icons/Terminal.svelte';
	import ChevronRight from '$lib/components/icons/ChevronRight.svelte';
	import ChevronLeft from '$lib/components/icons/ChevronLeft.svelte';

	const i18n = getContext('i18n');

	export let selectedToolIds: string[] = [];

	export let selectedModels: string[] = [];
	export let fileUploadCapableModels: string[] = [];

	export let toggleFilters: { id: string; name: string; description?: string; icon?: string }[] =
		[];
	export let selectedFilterIds: string[] = [];

export let showWebSearchButton = false;
export let webSearchEnabled = false;
export let showReasoningButton = false;
export let reasoningEnabled = false;
// Reasoning effort support & selection
export let reasoningEffort: string | null = 'medium'; // default to medium
let showReasoningEffort = false;
let allSelectedModelsSupportReasoningEffort = false;
let showEffortMenu = false;
let hideEffortMenuTimer: ReturnType<typeof setTimeout> | null = null;
export let showImageGenerationButton = false;
export let imageGenerationEnabled = false;
	export let showCodeInterpreterButton = false;
	export let codeInterpreterEnabled = false;

	export let onShowValves: Function;
	export let onClose: Function;

	let show = false;
	let tab = '';

	let tools = null;

	$: if (show) {
		init();
	}

	let fileUploadEnabled = true;
	$: fileUploadEnabled =
		fileUploadCapableModels.length === selectedModels.length &&
		($user?.role === 'admin' || $user?.permissions?.chat?.file_upload);

	const init = async () => {
		if ($_tools === null) {
			await _tools.set(await getTools(localStorage.token));
		}

		if ($_tools) {
			tools = $_tools.reduce((a, tool, i, arr) => {
				a[tool.id] = {
					name: tool.name,
					description: tool.meta.description,
					enabled: selectedToolIds.includes(tool.id),
					...tool
				};
				return a;
			}, {});
		}

		if ($toolServers) {
			for (const serverIdx in $toolServers) {
				const server = $toolServers[serverIdx];
				if (server.info) {
					tools[`direct_server:${serverIdx}`] = {
						name: server?.info?.title ?? server.url,
						description: server.info.description ?? '',
						enabled: selectedToolIds.includes(`direct_server:${serverIdx}`)
					};
				}
			}
		}

		selectedToolIds = selectedToolIds.filter((id) => Object.keys(tools).includes(id));
	};

    // Local visibility derived from selectedModels to avoid stale parent gating
    $: showReasoningLocal = (selectedModels ?? []).some((id) => {
        const m = $models.find((mm) => mm.id === id);
        return Boolean(m?.info?.meta?.capabilities?.reasoning ?? false);
    });

    // Compute whether to show Reasoning Effort selector
    $: {
        const currentModelIds = selectedModels;
        // Show effort whenever at least one current model supports reasoning
        const anyReasoning = showReasoningLocal;
        allSelectedModelsSupportReasoningEffort = anyReasoning;
        showReasoningEffort = (showReasoningButton ?? true) && anyReasoning;
        if (!showReasoningEffort) {
            reasoningEffort = null;
        } else if (reasoningEffort == null) {
            reasoningEffort = 'medium';
        }
    }
</script>

<Dropdown
	bind:show
	on:change={(e) => {
		if (e.detail === false) {
			onClose();
		}
	}}
>
	<Tooltip content={$i18n.t('Integrations')} placement="top">
		<slot />
	</Tooltip>
	<div slot="content">
		<DropdownMenu.Content
						class="w-full max-w-70 rounded-2xl px-1 py-1  border border-gray-100  dark:border-gray-800 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-lg max-h-72 overflow-y-auto overflow-x-visible md:overflow-visible scrollbar-thin"
			sideOffset={4}
			alignOffset={-6}
			side="bottom"
			align="start"
			transition={flyAndScale}
		>
			{#if tab === ''}
				<div in:fly={{ x: -20, duration: 150 }}>
					{#if tools}
						{#if Object.keys(tools).length > 0}
								<button
									class="flex w-full justify-between gap-2 items-center px-3 py-1.5 text-sm cursor-pointer rounded-xl hover:bg-gray-50 dark:hover:bg-gray-800/50"
									on:click={() => {
										tab = 'tools';
								}}
							>
								<Wrench />

								<div class="flex items-center w-full justify-between">
									<div class=" line-clamp-1">
										{$i18n.t('Tools')}
										<span class="ml-0.5 text-gray-500">{Object.keys(tools).length}</span>
									</div>

									<div class="text-gray-500">
										<ChevronRight />
									</div>
								</div>
							</button>
						{/if}
					{:else}
						<div class="py-4">
							<Spinner />
						</div>
					{/if}

					{#if toggleFilters && toggleFilters.length > 0}
						{#each toggleFilters.sort( (a, b) => a.name.localeCompare( b.name, undefined, { sensitivity: 'base' } ) ) as filter, filterIdx (filter.id)}
							<Tooltip content={filter?.description} placement="top-start">
								<button
									class="flex w-full justify-between gap-2 items-center px-3 py-1.5 text-sm cursor-pointer rounded-xl hover:bg-gray-50 dark:hover:bg-gray-800/50"
									on:click={() => {
										if (selectedFilterIds.includes(filter.id)) {
											selectedFilterIds = selectedFilterIds.filter((id) => id !== filter.id);
										} else {
											selectedFilterIds = [...selectedFilterIds, filter.id];
										}
									}}
								>
									<div class="flex-1 truncate">
										<div class="flex flex-1 gap-2 items-center">
											<div class="shrink-0">
												{#if filter?.icon}
													<div class="size-4 items-center flex justify-center">
														<img
															src={filter.icon}
															class="size-3.5 {filter.icon.includes('svg')
																? 'dark:invert-[80%]'
																: ''}"
															style="fill: currentColor;"
															alt={filter.name}
														/>
													</div>
												{:else}
													<Sparkles className="size-4" strokeWidth="1.75" />
												{/if}
											</div>

											<div class=" truncate">{filter?.name}</div>
										</div>
									</div>

									{#if filter?.has_user_valves}
										<div class=" shrink-0">
											<Tooltip content={$i18n.t('Valves')}>
												<button
													class="self-center w-fit text-sm text-gray-600 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition rounded-full"
													type="button"
													on:click={(e) => {
														e.stopPropagation();
														e.preventDefault();
														onShowValves({
															type: 'function',
															id: filter.id
														});
													}}
												>
													<Knobs />
												</button>
											</Tooltip>
										</div>
									{/if}

									<div class=" shrink-0">
										<Switch
											state={selectedFilterIds.includes(filter.id)}
											on:change={async (e) => {
												const state = e.detail;
												await tick();
											}}
										/>
									</div>
								</button>
							</Tooltip>
						{/each}
					{/if}

					{#if showReasoningLocal}
						<div class="group/rsn">
							<Tooltip content={$i18n.t('Enable structured reasoning')} placement="top-start">
								<button
									class="flex w-full justify-between gap-2 items-center px-3 py-1.5 text-sm cursor-pointer rounded-xl hover:bg-gray-50 dark:hover:bg-gray-800/50"
									on:click={() => {
										reasoningEnabled = !reasoningEnabled;
										if (reasoningEnabled && reasoningEffort == null) {
											reasoningEffort = 'medium';
										}
									}}
								>
									<div class="flex-1 truncate">
										<div class="flex flex-1 gap-2 items-center">
											<div class="shrink-0">
												<Sparkles />
											</div>

											<div class=" truncate">{$i18n.t('Reasoning')}</div>
										</div>
									</div>

									<div class=" shrink-0">
										<Switch
											state={reasoningEnabled}
											on:change={async (e) => {
												const state = e.detail;
												await tick();
											}}
										/>
									</div>
								</button>
							</Tooltip>

                            {#if showReasoningEffort}
                                <div class="relative">
                            <button
                                class="flex w-full justify-between gap-2 items-center px-3 py-1.5 text-sm cursor-pointer rounded-xl hover:bg-gray-50 dark:hover:bg-gray-800/50"
                                on:mouseenter={() => { if (hideEffortMenuTimer) clearTimeout(hideEffortMenuTimer); showEffortMenu = true; }}
                                                                on:mouseleave={() => { hideEffortMenuTimer = setTimeout(() => { showEffortMenu = false; hideEffortMenuTimer = null; }, 150); }}
                                aria-haspopup="menu"
                                type="button"
                            >
                                        <div class="flex-1 truncate">
                                            <div class="flex flex-1 gap-2 items-center">
                                        <div class="shrink-0">
                                            <Brain level={reasoningEffort ?? 'medium'} />
                                        </div>
                                                <div class="truncate">{$i18n.t('Effort')}</div>
                                            </div>
                                        </div>
                                        <div class="shrink-0 text-gray-400">▶</div>
                                    </button>

                                    {#if showEffortMenu}
                                        <div
                                            class="absolute left-full top-0 ml-0 w-44 rounded-xl px-2 py-2 border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-850 shadow-lg z-[60]"
                                            role="menu"
                                            aria-label={$i18n.t('Reasoning Effort')}
                                            on:mouseenter={() => { if (hideEffortMenuTimer) clearTimeout(hideEffortMenuTimer); showEffortMenu = true; }}
                                            on:mouseleave={() => { hideEffortMenuTimer = setTimeout(() => (showEffortMenu = false), 150); }}
                                        >
                                            <div class="text-xs text-gray-600 dark:text-gray-400 px-1 pb-1 flex items-center gap-1">
                                                <Brain className="size-3.5" strokeWidth="1.5" level={reasoningEffort ?? 'medium'} />
                                                {$i18n.t('Reasoning Effort')}
                                            </div>
                                            <div class="flex flex-col gap-1">
                                                <button
                                                    class="flex items-center gap-2 px-2 py-1 rounded-lg text-xs transition w-full text-left {reasoningEffort === 'low' ? 'bg-gray-900 text-white dark:bg-white dark:text-black' : 'hover:bg-gray-100 dark:hover:bg-gray-800'}"
                                                    on:click|preventDefault={() => (reasoningEffort = 'low')}
                                                    type="button"
                                                >
                                                    <Brain className="size-3.5" strokeWidth="1.75" level="low" />
                                                    <span>{$i18n.t('Low')}</span>
                                                </button>
                                                <button
                                                    class="flex items-center gap-2 px-2 py-1 rounded-lg text-xs transition w-full text-left {reasoningEffort === 'medium' ? 'bg-gray-900 text-white dark:bg-white dark:text-black' : 'hover:bg-gray-100 dark:hover:bg-gray-800'}"
                                                    on:click|preventDefault={() => (reasoningEffort = 'medium')}
                                                    type="button"
                                                >
                                                    <Brain className="size-3.5" strokeWidth="1.75" level="medium" />
                                                    <span>{$i18n.t('Medium')}</span>
                                                </button>
                                                <button
                                                    class="flex items-center gap-2 px-2 py-1 rounded-lg text-xs transition w-full text-left {reasoningEffort === 'high' ? 'bg-gray-900 text-white dark:bg-white dark:text-black' : 'hover:bg-gray-100 dark:hover:bg-gray-800'}"
                                                    on:click|preventDefault={() => (reasoningEffort = 'high')}
                                                    type="button"
                                                >
                                                    <Brain className="size-3.5" strokeWidth="1.75" level="high" />
                                                    <span>{$i18n.t('High')}</span>
                                                </button>
                                            </div>
                                        </div>
                                    {/if}
                                </div>
                            {/if}
                        </div>
					{/if}

					{#if showWebSearchButton}
						<Tooltip content={$i18n.t('Search the internet')} placement="top-start">
							<button
								class="flex w-full justify-between gap-2 items-center px-3 py-1.5 text-sm cursor-pointer rounded-xl hover:bg-gray-50 dark:hover:bg-gray-800/50"
								on:click={() => {
									webSearchEnabled = !webSearchEnabled;
								}}
							>
								<div class="flex-1 truncate">
									<div class="flex flex-1 gap-2 items-center">
										<div class="shrink-0">
											<GlobeAlt />
										</div>

										<div class=" truncate">{$i18n.t('Web Search')}</div>
									</div>
								</div>

								<div class=" shrink-0">
									<Switch
										state={webSearchEnabled}
										on:change={async (e) => {
											const state = e.detail;
											await tick();
										}}
									/>
								</div>
							</button>
						</Tooltip>
					{/if}

					{#if showImageGenerationButton}
						<Tooltip content={$i18n.t('Generate an image')} placement="top-start">
							<button
								class="flex w-full justify-between gap-2 items-center px-3 py-1.5 text-sm cursor-pointer rounded-xl hover:bg-gray-50 dark:hover:bg-gray-800/50"
								on:click={() => {
									imageGenerationEnabled = !imageGenerationEnabled;
								}}
							>
								<div class="flex-1 truncate">
									<div class="flex flex-1 gap-2 items-center">
										<div class="shrink-0">
											<Photo className="size-4" strokeWidth="1.5" />
										</div>

										<div class=" truncate">{$i18n.t('Image')}</div>
									</div>
								</div>

								<div class=" shrink-0">
									<Switch
										state={imageGenerationEnabled}
										on:change={async (e) => {
											const state = e.detail;
											await tick();
										}}
									/>
								</div>
							</button>
						</Tooltip>
					{/if}

					{#if showCodeInterpreterButton}
						<Tooltip content={$i18n.t('Execute code for analysis')} placement="top-start">
							<button
								class="flex w-full justify-between gap-2 items-center px-3 py-1.5 text-sm cursor-pointer rounded-xl hover:bg-gray-50 dark:hover:bg-gray-800/50"
								aria-pressed={codeInterpreterEnabled}
								aria-label={codeInterpreterEnabled
									? $i18n.t('Disable Code Interpreter')
									: $i18n.t('Enable Code Interpreter')}
								on:click={() => {
									codeInterpreterEnabled = !codeInterpreterEnabled;
								}}
							>
								<div class="flex-1 truncate">
									<div class="flex flex-1 gap-2 items-center">
										<div class="shrink-0">
											<Terminal className="size-3.5" strokeWidth="1.75" />
										</div>

										<div class=" truncate">{$i18n.t('Code Interpreter')}</div>
									</div>
								</div>

								<div class=" shrink-0">
									<Switch
										state={codeInterpreterEnabled}
										on:change={async (e) => {
											const state = e.detail;
											await tick();
										}}
									/>
								</div>
							</button>
						</Tooltip>
					{/if}
				</div>
			{:else if tab === 'tools' && tools}
				<div in:fly={{ x: 20, duration: 150 }}>
					<button
						class="flex w-full justify-between gap-2 items-center px-3 py-1.5 text-sm cursor-pointer rounded-xl hover:bg-gray-50 dark:hover:bg-gray-800/50"
						on:click={() => {
							tab = '';
						}}
					>
						<ChevronLeft />

						<div class="flex items-center w-full justify-between">
							<div>
								{$i18n.t('Tools')}
								<span class="ml-0.5 text-gray-500">{Object.keys(tools).length}</span>
							</div>
						</div>
					</button>

					{#each Object.keys(tools) as toolId}
						<button
							class="relative flex w-full justify-between gap-2 items-center px-3 py-1.5 text-sm cursor-pointer rounded-xl hover:bg-gray-50 dark:hover:bg-gray-800/50"
							on:click={(e) => {
								if (!(tools[toolId]?.authenticated ?? true)) {
									e.preventDefault();

									let parts = toolId.split(':');
									let serverId = parts?.at(-1) ?? toolId;

									const authUrl = getOAuthClientAuthorizationUrl(serverId, 'mcp');
									window.open(authUrl, '_blank', 'noopener');
								} else {
									tools[toolId].enabled = !tools[toolId].enabled;
								}
							}}
						>
							{#if !(tools[toolId]?.authenticated ?? true)}
								<!-- make it slighly darker and not clickable -->
								<div class="absolute inset-0 opacity-50 rounded-xl cursor-pointer z-10" />
							{/if}
							<div class="flex-1 truncate">
								<div class="flex flex-1 gap-2 items-center">
									<Tooltip content={tools[toolId]?.name ?? ''} placement="top">
										<div class="shrink-0">
											<Wrench />
										</div>
									</Tooltip>
									<Tooltip content={tools[toolId]?.description ?? ''} placement="top-start">
										<div class=" truncate">{tools[toolId].name}</div>
									</Tooltip>
								</div>
							</div>

							{#if tools[toolId]?.has_user_valves}
								<div class=" shrink-0">
									<Tooltip content={$i18n.t('Valves')}>
										<button
											class="self-center w-fit text-sm text-gray-600 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition rounded-full"
											type="button"
											on:click={(e) => {
												e.stopPropagation();
												e.preventDefault();
												onShowValves({
													type: 'tool',
													id: toolId
												});
											}}
										>
											<Knobs />
										</button>
									</Tooltip>
								</div>
							{/if}

							<div class=" shrink-0">
								<Switch
									state={tools[toolId].enabled}
									on:change={async (e) => {
										const state = e.detail;
										await tick();
										if (state) {
											selectedToolIds = [...selectedToolIds, toolId];
										} else {
											selectedToolIds = selectedToolIds.filter((id) => id !== toolId);
										}
									}}
								/>
							</div>
						</button>
					{/each}
				</div>
			{/if}
		</DropdownMenu.Content>
	</div>
</Dropdown>
