<template>
  <div class="d-flex align-center justify-space-between mb-4" :class="{ 'mt-4': !isFirst }">
    <div>
      <div class="text-subtitle-1 font-weight-bold">
        <v-icon class="mr-1">{{ mapTypeConfig.icon }}</v-icon>
        {{ mapTypeConfig.title }}
      </div>
      <div class="text-caption text-medium-emphasis">
        {{ tileCount }} tiles stored
      </div>
    </div>

    <div class="d-flex">
      <v-btn
        class="mr-2"
        color="error"
        :disabled="isDownloading || tileCount === 0"
        size="small"
        variant="outlined"
        @click="$emit('clear')"
      >
        <v-icon size="small">mdi-delete</v-icon>
      </v-btn>

      <v-btn
        color="primary"
        :disabled="isDownloading && downloadingMapType !== mapType"
        :loading="isDownloading && downloadingMapType === mapType"
        size="small"
        @click="$emit('download')"
      >
        <v-icon class="mr-1" size="small">mdi-download</v-icon>
        Download
      </v-btn>
    </div>
  </div>

  <v-progress-linear
    v-if="isDownloading && downloadingMapType === mapType"
    color="primary"
    height="8"
    :model-value="progress.percentage"
    rounded
    striped
  >
    <template #default>
      {{ progress.current }} / {{ progress.total }} tiles
    </template>
  </v-progress-linear>
</template>

<script setup>
  const props = defineProps({
    mapType: {
      type: String,
      required: true,
    },
    mapTypeConfig: {
      type: Object,
      required: true,
    },
    tileCount: {
      type: Number,
      default: 0,
    },
    isDownloading: {
      type: Boolean,
      default: false,
    },
    downloadingMapType: {
      type: String,
      default: '',
    },
    progress: {
      type: Object,
      default: () => ({ current: 0, total: 0, percentage: 0 }),
    },
    isFirst: {
      type: Boolean,
      default: false,
    },
  })

  defineEmits(['download', 'clear'])
</script>
