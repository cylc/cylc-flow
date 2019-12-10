query {
  workflows {
    id
    name
    taskProxies {
      id
      name
      cyclePoint
      state
      isHeld
      parents {
        id
      }
      jobs {
        id
        submitNum
        state
      }
    }
    families {
      proxies {
        id
      	name
        cyclePoint
        firstParent {
          id
        }
      }
    }
  }
}
