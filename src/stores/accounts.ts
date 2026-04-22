import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'

export interface Account {
  id: string
  nickname: string
  cookie_path: string
  proxy: string | null
  status: string
  last_login: string
  daily_post_limit: number
}

export const useAccountStore = defineStore('accounts', () => {
  const accounts = ref<Account[]>([])
  const loading = ref(false)

  async function fetchAccounts() {
    loading.value = true
    try {
      accounts.value = await invoke<Account[]>('get_accounts')
    } catch (e) {
      console.error('Failed to fetch accounts:', e)
    } finally {
      loading.value = false
    }
  }

  async function addAccount(account: Account) {
    try {
      await invoke('add_account', { account })
      await fetchAccounts()
    } catch (e) {
      console.error('Failed to add account:', e)
      throw e
    }
  }

  async function updateAccount(account: Account) {
    try {
      await invoke('update_account', { account })
      await fetchAccounts()
    } catch (e) {
      console.error('Failed to update account:', e)
      throw e
    }
  }

  async function deleteAccount(id: string) {
    try {
      await invoke('delete_account', { id })
      await fetchAccounts()
    } catch (e) {
      console.error('Failed to delete account:', e)
      throw e
    }
  }

  return { accounts, loading, fetchAccounts, addAccount, updateAccount, deleteAccount }
})
