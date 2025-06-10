<template>
  <v-app-bar class="px-4" color="#1a3a5c">
    <template #prepend>
      <div class="text-h6 font-weight-medium">Ol Pejeta Drone Tracker</div>
    </template>

    <v-spacer />

    <v-tabs
      v-model="activeTab"
      align-tabs="end"
      color="white"
    >
      <v-tab
        v-for="(item, index) in navItems"
        :key="index"
        class="text-white text-subtitle-1 font-weight-medium"
        :value="index"
      >
        {{ item.label }}
      </v-tab>
    </v-tabs>
  </v-app-bar>
</template>

<script>
  export default {
    name: 'AppHeader',
    data () {
      return {
        activeTab: 0,
        navItems: [
          { label: 'Dashboard' },
          { label: 'History' },
          { label: 'Settings' },
        ],
      }
    },
  }
</script>

<style scoped>
:deep(.v-tab) {
  text-transform: none;
  letter-spacing: normal;
  font-size:1.1rem !important;
}

:deep(.v-tabs) {
  margin-right: -16px; /* Compensate for the padding */
}
</style>
