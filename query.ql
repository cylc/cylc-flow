query {
  workflows {
    id
    name
    status
    taskProxies {
      id
      name
      cyclePoint
      state
      isHeld
      parents {
        id
        name
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
          name
        }
      }
    }
  }
}
