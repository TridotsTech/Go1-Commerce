


!function ( $, window, pluginName, undefined){
  var containerDefaults = {
    
    drag: true,
    
    drop: true,
    
    
    exclude: "",
    
    
    
    nested: true,
    
    vertical: true
  }, 
  groupDefaults = {
    
    
    
    
    afterMove: function ($placeholder, container, $closestItemOrContainer) {
    },
    
    containerPath: "",
    
    containerSelector: "ol, ul",
    
    distance: 0,
    
    
    delay: 0,
    
    handle: "",
    
    
    
    itemPath: "",
    
    itemSelector: "li",
    
    bodyClass: "dragging",
    
    draggedClass: "dragged",
    
    
    
    isValidTarget: function ($item, container) {
      return true
    },
    
    
    onCancel: function ($item, container, _super, event) {
    },
    
    
    onDrag: function ($item, position, _super, event) {
      $item.css(position)
    },
    
    
    
    
    
    onDragStart: function ($item, container, _super, event) {
      $item.css({
        height: $item.outerHeight(),
        width: $item.outerWidth()
      })
      $item.addClass(container.group.options.draggedClass)
      $("body").addClass(container.group.options.bodyClass)
    },
    
    onDrop: function ($item, container, _super, event) {
      $item.removeClass(container.group.options.draggedClass).removeAttr("style")
      $("body").removeClass(container.group.options.bodyClass)
    },
    
    
    onMousedown: function ($item, _super, event) {
      if (!event.target.nodeName.match(/^(input|select|textarea)$/i)) {
        event.preventDefault()
        return true
      }
    },
    
    placeholderClass: "placeholder",
    
    
    
    placeholder: '<li class="placeholder"></li>',
    
    
    pullPlaceholder: true,
    
    
    serialize: function ($parent, $children, parentIsContainer) {
      var result = $.extend({}, $parent.data())

      if(parentIsContainer)
        return [$children]
      else if ($children[0]){
        result.children = $children
      }

      delete result.subContainers
      delete result.sortable

      return result
    },
    
    
    tolerance: 0
  }, 
  containerGroups = {},
  groupCounter = 0,
  emptyBox = {
    left: 0,
    top: 0,
    bottom: 0,
    right:0
  },
  eventNames = {
    start: "touchstart.sortable mousedown.sortable",
    drop: "touchend.sortable touchcancel.sortable mouseup.sortable",
    drag: "touchmove.sortable mousemove.sortable",
    scroll: "scroll.sortable"
  },
  subContainerKey = "subContainers"

  function d(a,b) {
    var x = Math.max(0, a[0] - b[0], b[0] - a[1]),
    y = Math.max(0, a[2] - b[1], b[1] - a[3])
    return x+y;
  }

  function setDimensions(array, dimensions, tolerance, useOffset) {
    var i = array.length,
    offsetMethod = useOffset ? "offset" : "position"
    tolerance = tolerance || 0

    while(i--){
      var el = array[i].el ? array[i].el : $(array[i]),
      
      pos = el[offsetMethod]()
      pos.left += parseInt(el.css('margin-left'), 10)
      pos.top += parseInt(el.css('margin-top'),10)
      dimensions[i] = [
        pos.left - tolerance,
        pos.left + el.outerWidth() + tolerance,
        pos.top - tolerance,
        pos.top + el.outerHeight() + tolerance
      ]
    }
  }

  function getRelativePosition(pointer, element) {
    var offset = element.offset()
    return {
      left: pointer.left - offset.left,
      top: pointer.top - offset.top
    }
  }

  function sortByDistanceDesc(dimensions, pointer, lastPointer) {
    pointer = [pointer.left, pointer.top]
    lastPointer = lastPointer && [lastPointer.left, lastPointer.top]

    var dim,
    i = dimensions.length,
    distances = []

    while(i--){
      dim = dimensions[i]
      distances[i] = [i,d(dim,pointer), lastPointer && d(dim, lastPointer)]
    }
    distances = distances.sort(function  (a,b) {
      return b[1] - a[1] || b[2] - a[2] || b[0] - a[0]
    })

    
    return distances
  }

  function ContainerGroup(options) {
    this.options = $.extend({}, groupDefaults, options)
    this.containers = []

    if(!this.options.rootGroup){
      this.scrollProxy = $.proxy(this.scroll, this)
      this.dragProxy = $.proxy(this.drag, this)
      this.dropProxy = $.proxy(this.drop, this)
      this.placeholder = $(this.options.placeholder)

      if(!options.isValidTarget)
        this.options.isValidTarget = undefined
    }
  }

  ContainerGroup.get = function  (options) {
    if(!containerGroups[options.group]) {
      if(options.group === undefined)
        options.group = groupCounter ++

      containerGroups[options.group] = new ContainerGroup(options)
    }

    return containerGroups[options.group]
  }

  ContainerGroup.prototype = {
    dragInit: function  (e, itemContainer) {
      this.$document = $(itemContainer.el[0].ownerDocument)

      
      var closestItem = $(e.target).closest(this.options.itemSelector);
      
      
      if (closestItem.length) {
        this.item = closestItem;
        this.itemContainer = itemContainer;
        if (this.item.is(this.options.exclude) || !this.options.onMousedown(this.item, groupDefaults.onMousedown, e)) {
            return;
        }
        this.setPointer(e);
        this.toggleListeners('on');
        this.setupDelayTimer();
        this.dragInitDone = true;
      }
    },
    drag: function  (e) {
      if(!this.dragging){
        if(!this.distanceMet(e) || !this.delayMet)
          return

        this.options.onDragStart(this.item, this.itemContainer, groupDefaults.onDragStart, e)
        this.item.before(this.placeholder)
        this.dragging = true
      }

      this.setPointer(e)
      
      this.options.onDrag(this.item,
                          getRelativePosition(this.pointer, this.item.offsetParent()),
                          groupDefaults.onDrag,
                          e)

      var p = this.getPointer(e),
      box = this.sameResultBox,
      t = this.options.tolerance

      if(!box || box.top - t > p.top || box.bottom + t < p.top || box.left - t > p.left || box.right + t < p.left)
        if(!this.searchValidTarget()){
          this.placeholder.detach()
          this.lastAppendedItem = undefined
        }
    },
    drop: function  (e) {
      this.toggleListeners('off')

      this.dragInitDone = false

      if(this.dragging){
        
        if(this.placeholder.closest("html")[0]){
          this.placeholder.before(this.item).detach()
        } else {
          this.options.onCancel(this.item, this.itemContainer, groupDefaults.onCancel, e)
        }
        this.options.onDrop(this.item, this.getContainer(this.item), groupDefaults.onDrop, e)

        
        this.clearDimensions()
        this.clearOffsetParent()
        this.lastAppendedItem = this.sameResultBox = undefined
        this.dragging = false
      }
    },
    searchValidTarget: function  (pointer, lastPointer) {
      if(!pointer){
        pointer = this.relativePointer || this.pointer
        lastPointer = this.lastRelativePointer || this.lastPointer
      }

      var distances = sortByDistanceDesc(this.getContainerDimensions(),
                                         pointer,
                                         lastPointer),
      i = distances.length

      while(i--){
        var index = distances[i][0],
        distance = distances[i][1]

        if(!distance || this.options.pullPlaceholder){
          var container = this.containers[index]
          if(!container.disabled){
            if(!this.$getOffsetParent()){
              var offsetParent = container.getItemOffsetParent()
              pointer = getRelativePosition(pointer, offsetParent)
              lastPointer = getRelativePosition(lastPointer, offsetParent)
            }
            if(container.searchValidTarget(pointer, lastPointer))
              return true
          }
        }
      }
      if(this.sameResultBox)
        this.sameResultBox = undefined
    },
    movePlaceholder: function  (container, item, method, sameResultBox) {
      var lastAppendedItem = this.lastAppendedItem
      if(!sameResultBox && lastAppendedItem && lastAppendedItem[0] === item[0])
        return;

      item[method](this.placeholder)
      this.lastAppendedItem = item
      this.sameResultBox = sameResultBox
      this.options.afterMove(this.placeholder, container, item)
    },
    getContainerDimensions: function  () {
      if(!this.containerDimensions)
        setDimensions(this.containers, this.containerDimensions = [], this.options.tolerance, !this.$getOffsetParent())
      return this.containerDimensions
    },
    getContainer: function  (element) {
      return element.closest(this.options.containerSelector).data(pluginName)
    },
    $getOffsetParent: function  () {
      if(this.offsetParent === undefined){
        var i = this.containers.length - 1,
        offsetParent = this.containers[i].getItemOffsetParent()

        if(!this.options.rootGroup){
          while(i--){
            if(offsetParent[0] != this.containers[i].getItemOffsetParent()[0]){
              
              
              
              
              offsetParent = false
              break;
            }
          }
        }

        this.offsetParent = offsetParent
      }
      return this.offsetParent
    },
    setPointer: function (e) {
      var pointer = this.getPointer(e)

      if(this.$getOffsetParent()){
        var relativePointer = getRelativePosition(pointer, this.$getOffsetParent())
        this.lastRelativePointer = this.relativePointer
        this.relativePointer = relativePointer
      }

      this.lastPointer = this.pointer
      this.pointer = pointer
    },
    distanceMet: function (e) {
      var currentPointer = this.getPointer(e)
      return (Math.max(
        Math.abs(this.pointer.left - currentPointer.left),
        Math.abs(this.pointer.top - currentPointer.top)
      ) >= this.options.distance)
    },
    getPointer: function(e) {
      var o = e.originalEvent || e.originalEvent.touches && e.originalEvent.touches[0]
      return {
        left: e.pageX || o.pageX,
        top: e.pageY || o.pageY
      }
    },
    setupDelayTimer: function () {
      var that = this
      this.delayMet = !this.options.delay

      
      if (!this.delayMet) {
        clearTimeout(this._mouseDelayTimer);
        this._mouseDelayTimer = setTimeout(function() {
          that.delayMet = true
        }, this.options.delay)
      }
    },
    scroll: function  (e) {
      this.clearDimensions()
      this.clearOffsetParent() 
    },
    toggleListeners: function (method) {
      var that = this,
      events = ['drag','drop','scroll']

      $.each(events,function  (i,event) {
        that.$document[method](eventNames[event], that[event + 'Proxy'])
      })
    },
    clearOffsetParent: function () {
      this.offsetParent = undefined
    },
    
    clearDimensions: function  () {
      this.traverse(function(object){
        object._clearDimensions()
      })
    },
    traverse: function(callback) {
      callback(this)
      var i = this.containers.length
      while(i--){
        this.containers[i].traverse(callback)
      }
    },
    _clearDimensions: function(){
      this.containerDimensions = undefined
    },
    _destroy: function () {
      containerGroups[this.options.group] = undefined
    }
  }

  function Container(element, options) {
    this.el = element
    this.options = $.extend( {}, containerDefaults, options)

    this.group = ContainerGroup.get(this.options)
    this.rootGroup = this.options.rootGroup || this.group
    this.handle = this.rootGroup.options.handle || this.rootGroup.options.itemSelector

    var itemPath = this.rootGroup.options.itemPath
    this.target = itemPath ? this.el.find(itemPath) : this.el

    this.target.on(eventNames.start, this.handle, $.proxy(this.dragInit, this))

    if(this.options.drop)
      this.group.containers.push(this)
  }

  Container.prototype = {
    dragInit: function  (e) {
      var rootGroup = this.rootGroup

      if( !this.disabled &&
          !rootGroup.dragInitDone &&
          this.options.drag &&
          this.isValidDrag(e)) {
        rootGroup.dragInit(e, this)
      }
    },
    isValidDrag: function(e) {
      return e.which == 1 ||
        e.type == "touchstart" && e.originalEvent.touches.length == 1
    },
    searchValidTarget: function  (pointer, lastPointer) {
      var distances = sortByDistanceDesc(this.getItemDimensions(),
                                         pointer,
                                         lastPointer),
      i = distances.length,
      rootGroup = this.rootGroup,
      validTarget = !rootGroup.options.isValidTarget ||
        rootGroup.options.isValidTarget(rootGroup.item, this)

      if(!i && validTarget){
        rootGroup.movePlaceholder(this, this.target, "append")
        return true
      } else
        while(i--){
          var index = distances[i][0],
          distance = distances[i][1]
          if(!distance && this.hasChildGroup(index)){
            var found = this.getContainerGroup(index).searchValidTarget(pointer, lastPointer)
            if(found)
              return true
          }
          else if(validTarget){
            this.movePlaceholder(index, pointer)
            return true
          }
        }
    },
    movePlaceholder: function  (index, pointer) {
      var item = $(this.items[index]),
      dim = this.itemDimensions[index],
      method = "after",
      width = item.outerWidth(),
      height = item.outerHeight(),
      offset = item.offset(),
      sameResultBox = {
        left: offset.left,
        right: offset.left + width,
        top: offset.top,
        bottom: offset.top + height
      }
      if(this.options.vertical){
        var yCenter = (dim[2] + dim[3]) / 2,
        inUpperHalf = pointer.top <= yCenter
        if(inUpperHalf){
          method = "before"
          sameResultBox.bottom -= height / 2
        } else
          sameResultBox.top += height / 2
      } else {
        var xCenter = (dim[0] + dim[1]) / 2,
        inLeftHalf = pointer.left <= xCenter
        if(inLeftHalf){
          method = "before"
          sameResultBox.right -= width / 2
        } else
          sameResultBox.left += width / 2
      }
      if(this.hasChildGroup(index))
        sameResultBox = emptyBox
      this.rootGroup.movePlaceholder(this, item, method, sameResultBox)
    },
    getItemDimensions: function  () {
      if(!this.itemDimensions){
        this.items = this.$getChildren(this.el, "item").filter(
          ":not(." + this.group.options.placeholderClass + ", ." + this.group.options.draggedClass + ")"
        ).get()
        setDimensions(this.items, this.itemDimensions = [], this.options.tolerance)
      }
      return this.itemDimensions
    },
    getItemOffsetParent: function  () {
      var offsetParent,
      el = this.el
      
      
      if(el.css("position") === "relative" || el.css("position") === "absolute"  || el.css("position") === "fixed")
        offsetParent = el
      else
        offsetParent = el.offsetParent()
      return offsetParent
    },
    hasChildGroup: function (index) {
      return this.options.nested && this.getContainerGroup(index)
    },
    getContainerGroup: function  (index) {
      var childGroup = $.data(this.items[index], subContainerKey)
      if( childGroup === undefined){
        var childContainers = this.$getChildren(this.items[index], "container")
        childGroup = false

        if(childContainers[0]){
          var options = $.extend({}, this.options, {
            rootGroup: this.rootGroup,
            group: groupCounter ++
          })
          childGroup = childContainers[pluginName](options).data(pluginName).group
        }
        $.data(this.items[index], subContainerKey, childGroup)
      }
      return childGroup
    },
    $getChildren: function (parent, type) {
      var options = this.rootGroup.options,
      path = options[type + "Path"],
      selector = options[type + "Selector"]

      parent = $(parent)
      if(path)
        parent = parent.find(path)

      return parent.children(selector)
    },
    _serialize: function (parent, isContainer) {
      var that = this,
      childType = isContainer ? "item" : "container",

      children = this.$getChildren(parent, childType).not(this.options.exclude).map(function () {
        return that._serialize($(this), !isContainer)
      }).get()

      return this.rootGroup.options.serialize(parent, children, isContainer)
    },
    traverse: function(callback) {
      $.each(this.items || [], function(item){
        var group = $.data(this, subContainerKey)
        if(group)
          group.traverse(callback)
      });

      callback(this)
    },
    _clearDimensions: function  () {
      this.itemDimensions = undefined
    },
    _destroy: function() {
      var that = this;

      this.target.off(eventNames.start, this.handle);
      this.el.removeData(pluginName)

      if(this.options.drop)
        this.group.containers = $.grep(this.group.containers, function(val){
          return val != that
        })

      $.each(this.items || [], function(){
        $.removeData(this, subContainerKey)
      })
    }
  }

  var API = {
    enable: function() {
      this.traverse(function(object){
        object.disabled = false
      })
    },
    disable: function (){
      this.traverse(function(object){
        object.disabled = true
      })
    },
    serialize: function () {
      return this._serialize(this.el, true)
    },
    refresh: function() {
      this.traverse(function(object){
        object._clearDimensions()
      })
    },
    destroy: function () {
      this.traverse(function(object){
        object._destroy();
      })
    }
  }

  $.extend(Container.prototype, API)


  $.fn[pluginName] = function(methodOrOptions) {
    var args = Array.prototype.slice.call(arguments, 1)

    return this.map(function(){
      var $t = $(this),
      object = $t.data(pluginName)

      if(object && API[methodOrOptions])
        return API[methodOrOptions].apply(object, args) || this
      else if(!object && (methodOrOptions === undefined ||
                          typeof methodOrOptions === "object"))
        $t.data(pluginName, new Container($t, methodOrOptions))

      return this
    });
  };

}(jQuery, window, 'sortable');